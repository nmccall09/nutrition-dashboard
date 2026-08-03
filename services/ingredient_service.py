from typing import Any

import pandas as pd

from database.connection import (
    get_connection,
    query_dataframe,
)


def add_ingredient(
    ingredient_name: str,
    category: str,
    preferred_store: str,
    default_unit: str,
    estimated_unit_cost: float,
) -> int:
    query = """
        INSERT INTO ingredients (
            ingredient_name,
            category,
            preferred_store,
            default_unit,
            estimated_unit_cost
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING ingredient_id
    """

    with get_connection() as connection:
        try:
            row = connection.execute(
                query,
                (
                    ingredient_name.strip(),
                    category.strip(),
                    preferred_store,
                    default_unit.strip(),
                    estimated_unit_cost,
                ),
            ).fetchone()

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    if row is None:
        raise RuntimeError(
            "PostgreSQL did not return an ingredient ID."
        )

    return int(row["ingredient_id"])


def get_all_ingredients(
    include_archived: bool = False,
) -> pd.DataFrame:
    query = """
        SELECT
            ingredient_id,
            ingredient_name,
            category,
            preferred_store,
            default_unit,
            estimated_unit_cost,
            package_quantity,
            package_unit,
            package_price,
            package_description,
            is_active
        FROM ingredients
    """

    if not include_archived:
        query += """
        WHERE is_active = 1
        """

    query += """
        ORDER BY ingredient_name
    """

    with get_connection() as connection:
        return query_dataframe(query)


def get_ingredient_by_id(
    ingredient_id: int,
) -> dict[str, Any] | None:
    """
    Return one ingredient.
    """
    query = """
        SELECT *
        FROM ingredients
        WHERE ingredient_id = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (ingredient_id,),
        ).fetchone()

    return dict(row) if row else None


def add_ingredient_to_recipe(
    recipe_id: int,
    ingredient_id: int,
    quantity: float,
    unit: str,
    estimated_cost: float,
) -> int:
    query = """
        INSERT INTO recipe_ingredients (
            recipe_id,
            ingredient_id,
            quantity,
            unit,
            estimated_cost
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING recipe_ingredient_id
    """

    with get_connection() as connection:
        try:
            row = connection.execute(
                query,
                (
                    recipe_id,
                    ingredient_id,
                    quantity,
                    unit.strip(),
                    estimated_cost,
                ),
            ).fetchone()

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    if row is None:
        raise RuntimeError(
            "PostgreSQL did not return a recipe "
            "ingredient assignment ID."
        )

    return int(
        row["recipe_ingredient_id"]
    )


def get_recipe_ingredients(
    recipe_id: int,
) -> pd.DataFrame:
    """
    Return all ingredients assigned to one recipe.
    """
    query = """
        SELECT
            ri.recipe_ingredient_id,
            i.ingredient_name,
            i.category,
            i.preferred_store,
            ri.quantity,
            ri.unit,
            ri.estimated_cost
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i
            ON ri.ingredient_id = i.ingredient_id
        WHERE ri.recipe_id = %s
        ORDER BY i.ingredient_name
    """

    with get_connection() as connection:
        return query_dataframe(
            query,
            (recipe_id,),
        )

def get_recipe_ingredient_by_id(
    recipe_ingredient_id: int,
) -> dict[str, Any] | None:
    """
    Return one recipe-ingredient assignment.
    """
    query = """
        SELECT
            ri.recipe_ingredient_id,
            ri.recipe_id,
            ri.ingredient_id,
            i.ingredient_name,
            ri.quantity,
            ri.unit,
            ri.estimated_cost
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i
            ON ri.ingredient_id = i.ingredient_id
        WHERE ri.recipe_ingredient_id = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (recipe_ingredient_id,),
        ).fetchone()

    return dict(row) if row else None


def update_recipe_ingredient(
    recipe_ingredient_id: int,
    quantity: float,
    unit: str,
    estimated_cost: float,
) -> None:
    """
    Update an ingredient assignment for a recipe.
    """
    query = """
        UPDATE recipe_ingredients
        SET
            quantity = %s,
            unit = %s,
            estimated_cost = %s
        WHERE recipe_ingredient_id = %s
    """

    values = (
        quantity,
        unit.strip(),
        estimated_cost,
        recipe_ingredient_id,
    )

    with get_connection() as connection:
        cursor = connection.execute(query, values)
        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The recipe ingredient assignment was not found."
            )

def remove_ingredient_from_recipe(
    recipe_ingredient_id: int,
) -> None:
    """
    Remove an ingredient assignment from a recipe.
    """
    query = """
        DELETE FROM recipe_ingredients
        WHERE recipe_ingredient_id = %s
    """

    with get_connection() as connection:
        connection.execute(
            query,
            (recipe_ingredient_id,),
        )
        connection.commit()

def update_ingredient_package(
    ingredient_id: int,
    package_quantity: float | None,
    package_unit: str | None,
    package_price: float | None,
    package_description: str,
) -> None:
    """
    Save package purchasing information for an ingredient.

    Package quantity, unit, and price should either all be
    populated or all be left empty.
    """
    has_any_package_value = any(
        value is not None
        for value in (
            package_quantity,
            package_unit,
            package_price,
        )
    )

    has_all_package_values = all(
        value is not None
        for value in (
            package_quantity,
            package_unit,
            package_price,
        )
    )

    if has_any_package_value and not has_all_package_values:
        raise ValueError(
            "Package quantity, unit, and price must all "
            "be entered together."
        )

    if package_quantity is not None and package_quantity <= 0:
        raise ValueError(
            "Package quantity must be greater than zero."
        )

    if package_price is not None and package_price < 0:
        raise ValueError(
            "Package price cannot be negative."
        )

    query = """
        UPDATE ingredients
        SET
            package_quantity %s,
            package_unit = %s,
            package_price = %s,
            package_description = %s
        WHERE ingredient_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (
                package_quantity,
                (
                    package_unit.strip()
                    if package_unit
                    else None
                ),
                package_price,
                package_description.strip(),
                ingredient_id,
            ),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The ingredient could not be found."
            )

def clear_ingredient_package(
    ingredient_id: int,
) -> None:
    """
    Remove package purchasing information.
    """
    query = """
        UPDATE ingredients
        SET
            package_quantity = NULL,
            package_unit = NULL,
            package_price = NULL,
            package_description = NULL
        WHERE ingredient_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (ingredient_id,),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The ingredient could not be found."
            )

def get_ingredient_usage(
    ingredient_id: int,
) -> dict[str, int]:
    """
    Return counts showing where an ingredient is currently used.
    """
    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM recipe_ingredients
                WHERE ingredient_id = %s
            ) AS recipe_count,

            (
                SELECT COUNT(*)
                FROM pantry_inventory
                WHERE ingredient_id = %s
            ) AS pantry_count,

            (
                SELECT COUNT(*)
                FROM shopping_trip_items
                WHERE ingredient_id = %s
            ) AS shopping_trip_count
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (
                ingredient_id,
                ingredient_id,
                ingredient_id,
            ),
        ).fetchone()

    return {
        "recipe_count": int(row["recipe_count"] or 0),
        "pantry_count": int(row["pantry_count"] or 0),
        "shopping_trip_count": int(
            row["shopping_trip_count"] or 0
        ),
    }


def update_ingredient(
    ingredient_id: int,
    ingredient_name: str,
    category: str,
    preferred_store: str,
    default_unit: str,
    estimated_unit_cost: float,
) -> None:
    """
    Update the main details for an ingredient.
    """
    query = """
        UPDATE ingredients
        SET
            ingredient_name = %s,
            category = %s,
            preferred_store = %s,
            default_unit = %s,
            estimated_unit_cost = %s
        WHERE ingredient_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (
                ingredient_name.strip(),
                category.strip(),
                preferred_store,
                default_unit.strip(),
                estimated_unit_cost,
                ingredient_id,
            ),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The ingredient could not be found."
            )


def delete_ingredient(
    ingredient_id: int,
) -> None:
    """
    Delete an ingredient only when it is not referenced.
    """
    usage = get_ingredient_usage(ingredient_id)

    if usage["recipe_count"] > 0:
        raise ValueError(
            "Remove this ingredient from all recipes "
            "before deleting it."
        )

    if usage["pantry_count"] > 0:
        raise ValueError(
            "Remove this ingredient from the pantry "
            "before deleting it."
        )

    if usage["shopping_trip_count"] > 0:
        raise ValueError(
            "This ingredient is referenced by a saved "
            "shopping trip and cannot be deleted."
        )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM ingredients
            WHERE ingredient_id = %s
            """,
            (ingredient_id,),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The ingredient could not be found."
            )

def archive_ingredient(
    ingredient_id: int,
) -> None:
    """
    Remove an ingredient from active use while preserving
    historical shopping-trip records.
    """
    with get_connection() as connection:
        try:
            connection.execute(
                """
                DELETE FROM recipe_ingredients
                WHERE ingredient_id = %s
                """,
                (ingredient_id,),
            )

            connection.execute(
                """
                DELETE FROM pantry_inventory
                WHERE ingredient_id = %s
                """,
                (ingredient_id,),
            )

            cursor = connection.execute(
                """
                UPDATE ingredients
                SET is_active = 0
                WHERE ingredient_id = %s
                """,
                (ingredient_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "The ingredient could not be found."
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise


def restore_ingredient(
    ingredient_id: int,
) -> None:
    """
    Return an archived ingredient to active use.
    """
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE ingredients
            SET is_active = 1
            WHERE ingredient_id = %s
            """,
            (ingredient_id,),
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The ingredient could not be found."
            )