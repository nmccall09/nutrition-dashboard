from typing import Any

import pandas as pd

from database.connection import (
    get_connection,
    query_dataframe,
)


def add_recipe(
    recipe_name: str,
    meal_type: str,
    servings: float,
    calories_per_serving: float,
    protein_per_serving: float,
    carbs_per_serving: float,
    fat_per_serving: float,
    prep_minutes: int,
    estimated_cost_per_serving: float,
    instructions: str,
    notes: str,
) -> int:
    query = """
        INSERT INTO recipes (
            recipe_name,
            meal_type,
            servings,
            calories_per_serving,
            protein_per_serving,
            carbs_per_serving,
            fat_per_serving,
            prep_minutes,
            estimated_cost_per_serving,
            instructions,
            notes
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        RETURNING recipe_id
    """

    with get_connection() as connection:
        try:
            row = connection.execute(
                query,
                (
                    recipe_name.strip(),
                    meal_type,
                    servings,
                    calories_per_serving,
                    protein_per_serving,
                    carbs_per_serving,
                    fat_per_serving,
                    prep_minutes,
                    estimated_cost_per_serving,
                    instructions.strip(),
                    notes.strip(),
                ),
            ).fetchone()

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    if row is None:
        raise RuntimeError(
            "PostgreSQL did not return a recipe ID."
        )

    return int(row["recipe_id"])


def get_all_recipes() -> pd.DataFrame:
    query = """
        SELECT
            r.recipe_id,
            r.recipe_name,
            r.meal_type,
            r.servings,
            r.calories_per_serving,
            r.protein_per_serving,
            r.carbs_per_serving,
            r.fat_per_serving,
            r.prep_minutes,
            r.estimated_cost_per_serving
                AS manual_cost_per_serving,
            r.instructions,
            r.notes,
            r.created_at,
            r.updated_at,
            rcs.ingredient_count,
            rcs.total_ingredient_cost,
            rcs.effective_cost_per_serving

        FROM recipes AS r

        LEFT JOIN recipe_cost_summary AS rcs
            ON r.recipe_id = rcs.recipe_id

        ORDER BY
            r.recipe_name
    """

    return query_dataframe(query)


def get_recipe_by_id(
    recipe_id: int,
) -> dict | None:
    query = """
        SELECT
            r.recipe_id,
            r.recipe_name,
            r.meal_type,
            r.servings,
            r.calories_per_serving,
            r.protein_per_serving,
            r.carbs_per_serving,
            r.fat_per_serving,
            r.prep_minutes,
            r.estimated_cost_per_serving
                AS manual_cost_per_serving,
            r.instructions,
            r.notes,
            r.created_at,
            r.updated_at,
            rcs.ingredient_count,
            rcs.total_ingredient_cost,
            rcs.effective_cost_per_serving

        FROM recipes AS r

        LEFT JOIN recipe_cost_summary AS rcs
            ON r.recipe_id = rcs.recipe_id

        WHERE r.recipe_id = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (recipe_id,),
        ).fetchone()

    return dict(row) if row else None

def update_recipe(
    recipe_id: int,
    recipe_name: str,
    meal_type: str,
    servings: float,
    calories_per_serving: float,
    protein_per_serving: float,
    carbs_per_serving: float,
    fat_per_serving: float,
    prep_minutes: int,
    estimated_cost_per_serving: float,
    instructions: str,
    notes: str,
) -> None:
    query = """
        UPDATE recipes
        SET
            recipe_name = %s,
            meal_type = %s,
            servings = %s,
            calories_per_serving = %s,
            protein_per_serving = %s,
            carbs_per_serving = %s,
            fat_per_serving = %s,
            prep_minutes = %s,
            estimated_cost_per_serving = %s,
            instructions = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE recipe_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (
                recipe_name.strip(),
                meal_type,
                servings,
                calories_per_serving,
                protein_per_serving,
                carbs_per_serving,
                fat_per_serving,
                prep_minutes,
                estimated_cost_per_serving,
                instructions.strip(),
                notes.strip(),
                recipe_id,
            ),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The recipe could not be found."
            )


def delete_recipe(
    recipe_id: int,
) -> None:
    query = """
        DELETE FROM recipes
        WHERE recipe_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (recipe_id,),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The recipe could not be found."
            )