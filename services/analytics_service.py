from datetime import date

import pandas as pd

from database.connection import (
    get_connection,
    query_dataframe,
)


def get_recipe_analytics() -> pd.DataFrame:
    """
    Return recipe nutrition, cost, and usage analytics.
    """
    query = """
        SELECT
            r.recipe_id,
            r.recipe_name,
            r.meal_type,
            r.calories_per_serving,
            r.protein_per_serving,
            r.carbs_per_serving,
            r.fat_per_serving,
            r.prep_minutes,

            rcs.effective_cost_per_serving,
            rcs.ingredient_count,

            COUNT(ml.meal_log_id)
                AS times_logged,

            COALESCE(
                SUM(ml.servings),
                0
            ) AS servings_logged,

            COALESCE(
                SUM(
                    r.protein_per_serving
                    * ml.servings
                ),
                0
            ) AS total_protein_consumed,

            COALESCE(
                SUM(
                    r.calories_per_serving
                    * ml.servings
                ),
                0
            ) AS total_calories_consumed

        FROM recipes AS r

        JOIN recipe_cost_summary AS rcs
            ON r.recipe_id = rcs.recipe_id

        LEFT JOIN meal_log AS ml
            ON r.recipe_id = ml.recipe_id

        GROUP BY
            r.recipe_id,
            r.recipe_name,
            r.meal_type,
            r.calories_per_serving,
            r.protein_per_serving,
            r.carbs_per_serving,
            r.fat_per_serving,
            r.prep_minutes,
            rcs.effective_cost_per_serving,
            rcs.ingredient_count

        ORDER BY r.recipe_name
    """

    result = query_dataframe(query)

    if result.empty:
        return result

    result["protein_per_100_calories"] = (
        result["protein_per_serving"]
        / result["calories_per_serving"]
        * 100
    )

    safe_cost = result[
        "effective_cost_per_serving"
    ].replace(
        0,
        float("nan"),
    )

    result["protein_per_dollar"] = (
        result["protein_per_serving"]
        / safe_cost
    ).fillna(0)

    result["cost_source"] = result[
        "ingredient_count"
    ].apply(
        lambda count: (
            "Ingredients"
            if count > 0
            else "Manual estimate"
        )
    )

    return result


def get_period_summary(
    start_date: date,
    end_date: date,
) -> dict[str, float]:
    """
    Return aggregate nutrition and cost for a date range.
    """
    query = """
        SELECT
            COUNT(ml.meal_log_id) AS meals_logged,

            COUNT(
                DISTINCT ml.meal_date
            ) AS days_logged,

            COALESCE(
                SUM(
                    COALESCE(
                        ml.calories_snapshot,
                        r.calories_per_serving
                            * ml.servings
                    )
                ),
                0
            ) AS calories,

            COALESCE(
                SUM(
                    COALESCE(
                        ml.protein_snapshot,
                        r.protein_per_serving
                            * ml.servings
                    )
                ),
                0
            ) AS protein,

            COALESCE(
                SUM(
                    COALESCE(
                        ml.cost_snapshot,
                        rcs.effective_cost_per_serving
                            * ml.servings
                    )
                ),
                0
            ) AS estimated_cost

        FROM meal_log AS ml

        JOIN recipes AS r
            ON ml.recipe_id = r.recipe_id

        JOIN recipe_cost_summary AS rcs
            ON ml.recipe_id = rcs.recipe_id

        WHERE ml.meal_date BETWEEN %s AND %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (
                start_date,
                end_date,
            ),
        ).fetchone()

    if row is None:
        return {
            "meals_logged": 0,
            "days_logged": 0,
            "calories": 0.0,
            "protein": 0.0,
            "estimated_cost": 0.0,
        }

    return {
        "meals_logged": int(
            row["meals_logged"] or 0
        ),
        "days_logged": int(
            row["days_logged"] or 0
        ),
        "calories": float(
            row["calories"] or 0
        ),
        "protein": float(
            row["protein"] or 0
        ),
        "estimated_cost": float(
            row["estimated_cost"] or 0
        ),
    }