from datetime import date

import pandas as pd

from database.connection import (
    get_connection,
    query_dataframe,
)
from services.meal_log_service import add_meal_log


def add_meal_plan_entry(
    plan_date: date,
    meal_type: str,
    recipe_id: int,
    servings: float,
    notes: str,
) -> int:
    query = """
        INSERT INTO meal_plan (
            plan_date,
            meal_type,
            recipe_id,
            servings,
            notes
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING meal_plan_id
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (
                plan_date,
                meal_type,
                recipe_id,
                servings,
                notes.strip(),
            ),
        ).fetchone()

        connection.commit()

    if row is None:
        raise RuntimeError(
            "PostgreSQL did not return a "
            "meal-plan ID."
        )

    return int(row["meal_plan_id"])


def get_meal_plan(
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Return planned meals with nutrition and cost.
    """
    query = """
        SELECT
            mp.meal_plan_id,
            mp.plan_date,
            mp.meal_type,
            mp.recipe_id,
            r.recipe_name,
            mp.servings,
            mp.is_logged,

            r.calories_per_serving
                * mp.servings AS calories,

            r.protein_per_serving
                * mp.servings AS protein,

            r.carbs_per_serving
                * mp.servings AS carbs,

            r.fat_per_serving
                * mp.servings AS fat,

            rcs.effective_cost_per_serving
                * mp.servings AS estimated_cost,

            mp.notes

        FROM meal_plan AS mp

        JOIN recipes AS r
            ON mp.recipe_id = r.recipe_id

        JOIN recipe_cost_summary AS rcs
            ON mp.recipe_id = rcs.recipe_id

        WHERE mp.plan_date BETWEEN %s AND %s

        ORDER BY
            mp.plan_date,
            CASE mp.meal_type
                WHEN 'Breakfast' THEN 1
                WHEN 'Lunch' THEN 2
                WHEN 'Dinner' THEN 3
                WHEN 'Snack' THEN 4
            END,
            mp.meal_plan_id
    """

    result = query_dataframe(
        query,
        (
            start_date,
            end_date,
        ),
    )

    if not result.empty:
        result["plan_date"] = pd.to_datetime(
            result["plan_date"]
        )

        result["created_at"] = pd.to_datetime(
            result["created_at"]
        )

    return result


def delete_meal_plan_entry(
    meal_plan_id: int,
) -> None:
    """
    Delete one planned meal.
    """
    query = """
        DELETE FROM meal_plan
        WHERE meal_plan_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (meal_plan_id,),
        )
        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The planned meal was not found."
            )


def clear_meal_plan(
    start_date: date,
    end_date: date,
) -> int:
    query = """
        DELETE FROM meal_plan
        WHERE plan_date BETWEEN %s AND %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (
                start_date,
                end_date,
            ),
        )

        connection.commit()

        return int(cursor.rowcount)

def get_meal_plan_entry(
    meal_plan_id: int,
) -> dict | None:
    query = """
        SELECT
            meal_plan_id,
            plan_date,
            meal_type,
            recipe_id,
            servings,
            notes,
            is_logged
        FROM meal_plan
        WHERE meal_plan_id = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (meal_plan_id,),
        ).fetchone()

    return dict(row) if row else None

def mark_meal_plan_entry_logged(
    meal_plan_id: int,
) -> None:
    query = """
        UPDATE meal_plan
        SET is_logged = 1
        WHERE meal_plan_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (meal_plan_id,),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The planned meal was not found."
            )

def log_planned_meal(
    meal_plan_id: int,
) -> int:
    """
    Copy one planned meal into the meal log and mark it logged.
    """
    planned_meal = get_meal_plan_entry(
        meal_plan_id
    )

    if planned_meal is None:
        raise ValueError(
            "The planned meal could not be found."
        )

    meal_date = planned_meal["plan_date"]

    if not isinstance(meal_date, date):
        meal_date = date.fromisoformat(
            str(meal_date)
        )

    meal_log_id, pantry_warnings = add_meal_log(
        meal_date=meal_date,
        meal_type=planned_meal["meal_type"],
        recipe_id=int(planned_meal["recipe_id"]),
        servings=float(planned_meal["servings"]),
        notes=(
            planned_meal["notes"]
            or "Logged from meal planner"
        ),
    )

    mark_meal_plan_entry_logged(
        meal_plan_id
    )

    return meal_log_id, pantry_warnings

def log_planned_meals_for_date(
    plan_date: date,
) -> tuple[int, list[str]]:
    """
    Log every unlogged planned meal for one date.
    """
    query = """
        SELECT meal_plan_id
        FROM meal_plan
        WHERE
            plan_date = %s
            AND is_logged = 0
        ORDER BY meal_plan_id
    """

    with get_connection() as connection:
        rows = connection.execute(
            query,
            (plan_date,),
        ).fetchall()

    logged_count = 0
    all_warnings: list[str] = []

    for row in rows:
        _, warnings = log_planned_meal(
            int(row["meal_plan_id"])
        )

        all_warnings.extend(warnings)
        logged_count += 1

    return logged_count, all_warnings