from datetime import date

import pandas as pd

from database.connection import (
    get_connection,
    query_dataframe,
)
from services.pantry_service import (
    deduct_recipe_from_pantry,
    restore_pantry_for_meal,
)

def add_meal_log(
    meal_date: date,
    meal_type: str,
    recipe_id: int,
    servings: float,
    notes: str,
) -> tuple[int, list[str]]:
    recipe_query = """
        SELECT
            r.calories_per_serving,
            r.protein_per_serving,
            r.carbs_per_serving,
            r.fat_per_serving,
            rcs.effective_cost_per_serving

        FROM recipes AS r

        JOIN recipe_cost_summary AS rcs
            ON r.recipe_id = rcs.recipe_id

        WHERE r.recipe_id = %s
    """

    insert_query = """
        INSERT INTO meal_log (
            meal_date,
            meal_type,
            recipe_id,
            servings,
            notes,
            calories_snapshot,
            protein_snapshot,
            carbs_snapshot,
            fat_snapshot,
            cost_snapshot,
            pantry_deducted
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, 0
        )
        RETURNING meal_log_id
    """

    with get_connection() as connection:
        try:
            recipe = connection.execute(
                recipe_query,
                (recipe_id,),
            ).fetchone()

            if recipe is None:
                raise ValueError(
                    f"No recipe exists with ID {recipe_id}."
                )

            row = connection.execute(
                insert_query,
                (
                    meal_date,
                    meal_type,
                    recipe_id,
                    servings,
                    notes.strip(),
                    (
                        float(
                            recipe[
                                "calories_per_serving"
                            ]
                        )
                        * servings
                    ),
                    (
                        float(
                            recipe[
                                "protein_per_serving"
                            ]
                        )
                        * servings
                    ),
                    (
                        float(
                            recipe[
                                "carbs_per_serving"
                            ]
                        )
                        * servings
                    ),
                    (
                        float(
                            recipe[
                                "fat_per_serving"
                            ]
                        )
                        * servings
                    ),
                    (
                        float(
                            recipe[
                                "effective_cost_per_serving"
                            ]
                            or 0
                        )
                        * servings
                    ),
                ),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "PostgreSQL did not return a "
                    "meal-log ID."
                )

            meal_log_id = int(
                row["meal_log_id"]
            )

            pantry_warnings = deduct_recipe_from_pantry(
                connection=connection,
                recipe_id=recipe_id,
                logged_servings=servings,
                meal_log_id=meal_log_id,
            )

            connection.execute(
                """
                UPDATE meal_log
                SET pantry_deducted = 1
                WHERE meal_log_id = %s
                """,
                (meal_log_id,),
            )

            connection.commit()

            return meal_log_id, pantry_warnings

        except Exception:
            connection.rollback()
            raise

def get_meal_log(
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    query = """
        SELECT
            ml.meal_log_id,
            ml.meal_date,
            ml.meal_type,
            ml.recipe_id,
            r.recipe_name,
            ml.servings,

            COALESCE(
                ml.calories_snapshot,
                r.calories_per_serving * ml.servings
            ) AS calories,

            COALESCE(
                ml.protein_snapshot,
                r.protein_per_serving * ml.servings
            ) AS protein,

            COALESCE(
                ml.carbs_snapshot,
                r.carbs_per_serving * ml.servings
            ) AS carbs,

            COALESCE(
                ml.fat_snapshot,
                r.fat_per_serving * ml.servings
            ) AS fat,

            COALESCE(
                ml.cost_snapshot,
                rcs.effective_cost_per_serving
                    * ml.servings
            ) AS estimated_cost,

            CASE
                WHEN ml.cost_snapshot IS NOT NULL
                    THEN 'Historical snapshot'
                WHEN rcs.ingredient_count > 0
                    THEN 'Current ingredients'
                ELSE 'Current manual estimate'
            END AS cost_source,

            ml.notes,
            ml.created_at

        FROM meal_log AS ml

        JOIN recipes AS r
            ON ml.recipe_id = r.recipe_id

        JOIN recipe_cost_summary AS rcs
            ON ml.recipe_id = rcs.recipe_id
    """

    conditions: list[str] = []
    params: list[date] = []

    if start_date is not None:
        conditions.append(
            "ml.meal_date >= %s"
        )
        params.append(start_date)

    if end_date is not None:
        conditions.append(
            "ml.meal_date <= %s"
        )
        params.append(end_date)

    if conditions:
        query += """
        WHERE
        """
        query += " AND ".join(conditions)

    query += """
        ORDER BY
            ml.meal_date DESC,
            ml.meal_log_id DESC
    """

    result = query_dataframe(
        query,
        tuple(params),
    )

    if not result.empty:
        result["meal_date"] = pd.to_datetime(
            result["meal_date"]
        )

        result["created_at"] = pd.to_datetime(
            result["created_at"]
        )

    return result

def delete_meal_log(
    meal_log_id: int,
) -> None:
    with get_connection() as connection:
        try:
            meal = connection.execute(
                """
                SELECT
                    meal_log_id,
                    pantry_deducted
                FROM meal_log
                WHERE meal_log_id = %s
                """,
                (meal_log_id,),
            ).fetchone()

            if meal is None:
                raise ValueError(
                    "The meal-log entry was not found."
                )

            if int(
                meal["pantry_deducted"] or 0
            ) == 1:
                restore_pantry_for_meal(
                    connection=connection,
                    meal_log_id=meal_log_id,
                )

            connection.execute(
                """
                DELETE FROM meal_log
                WHERE meal_log_id = %s
                """,
                (meal_log_id,),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

def get_daily_nutrition(
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Return one summarized row per calendar day.
    """
    query = """
        SELECT
            ml.meal_date,

            SUM(
                COALESCE(
                    ml.calories_snapshot,
                    r.calories_per_serving * ml.servings
                )
            ) AS calories,

            SUM(
                COALESCE(
                    ml.protein_snapshot,
                    r.protein_per_serving * ml.servings
                )
            ) AS protein,

            SUM(
                COALESCE(
                    ml.carbs_snapshot,
                    r.carbs_per_serving * ml.servings
                )
            ) AS carbs,

            SUM(
                COALESCE(
                    ml.fat_snapshot,
                    r.fat_per_serving * ml.servings
                )
            ) AS fat,

            SUM(
                COALESCE(
                    ml.cost_snapshot,
                    rcs.effective_cost_per_serving * ml.servings
                )
            ) AS estimated_cost,

            COUNT(*) AS meals_logged

        FROM meal_log AS ml

        JOIN recipes AS r
            ON ml.recipe_id = r.recipe_id

        JOIN recipe_cost_summary AS rcs
            ON ml.recipe_id = rcs.recipe_id

        WHERE ml.meal_date BETWEEN %s AND %s

        GROUP BY ml.meal_date

        ORDER BY ml.meal_date
    """

    return query_dataframe(
    query,
    (
        start_date,
        end_date,
    ),
)
