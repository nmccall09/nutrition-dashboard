from datetime import date

import pandas as pd
import psycopg

from database.connection import (
    get_connection,
    query_dataframe,
)
from services.unit_conversion_service import (
    can_convert_units,
    convert_quantity,
)


def upsert_pantry_item(
    ingredient_id: int,
    quantity_on_hand: float,
    unit: str,
    minimum_quantity: float,
    expiration_date: date | None,
    notes: str,
) -> None:
    """
    Add an ingredient to the pantry or update its current record.
    """
    query = """
        INSERT INTO pantry_inventory (
            ingredient_id,
            quantity_on_hand,
            unit,
            minimum_quantity,
            expiration_date,
            notes,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)

        ON CONFLICT(ingredient_id)
        DO UPDATE SET
            quantity_on_hand = excluded.quantity_on_hand,
            unit = excluded.unit,
            minimum_quantity = excluded.minimum_quantity,
            expiration_date = excluded.expiration_date,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
    """

    expiration_value = (
        expiration_date.isoformat()
        if expiration_date is not None
        else None
    )

    with get_connection() as connection:
        connection.execute(
            query,
            (
                ingredient_id,
                quantity_on_hand,
                unit.strip(),
                minimum_quantity,
                expiration_value,
                notes.strip(),
            ),
        )
        connection.commit()


def get_pantry_inventory() -> pd.DataFrame:
    """
    Return all pantry inventory with ingredient metadata.
    """
    query = """
        SELECT
            p.pantry_id,
            p.ingredient_id,
            i.ingredient_name,
            i.category,
            i.preferred_store,
            i.default_unit,
            p.quantity_on_hand,
            p.unit,
            p.minimum_quantity,
            p.expiration_date,
            p.notes,
            p.updated_at

        FROM pantry_inventory AS p

        JOIN ingredients AS i
            ON p.ingredient_id = i.ingredient_id

        ORDER BY
            i.category,
            i.ingredient_name
    """

    with get_connection() as connection:
        result = query_dataframe(query)

    if not result.empty:
        result["expiration_date"] = pd.to_datetime(
            result["expiration_date"],
            errors="coerce",
        )

        result["updated_at"] = pd.to_datetime(
            result["updated_at"],
            errors="coerce",
        )

    return result


def get_pantry_item(
    ingredient_id: int,
) -> dict | None:
    """
    Return one pantry record by ingredient.
    """
    query = """
        SELECT
            pantry_id,
            ingredient_id,
            quantity_on_hand,
            unit,
            minimum_quantity,
            expiration_date,
            notes
        FROM pantry_inventory
        WHERE ingredient_id = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (ingredient_id,),
        ).fetchone()

    return dict(row) if row else None


def delete_pantry_item(
    pantry_id: int,
) -> None:
    """
    Remove one item from pantry inventory.
    """
    query = """
        DELETE FROM pantry_inventory
        WHERE pantry_id = %s
    """

    with get_connection() as connection:
        cursor = connection.execute(
            query,
            (pantry_id,),
        )
        connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(
                "The pantry item was not found."
            )

def deduct_recipe_from_pantry(
    connection: psycopg.Connection,
    recipe_id: int,
    logged_servings: float,
    meal_log_id: int,
) -> list[str]:
    """
    Deduct recipe ingredients from pantry inventory.

    The recipe ingredient quantities represent the full recipe
    batch, so each deduction is scaled by:

        logged servings / recipe batch servings

    Returns warning messages for missing pantry items,
    unit mismatches, or insufficient quantities.
    """
    recipe_row = connection.execute(
        """
        SELECT servings
        FROM recipes
        WHERE recipe_id = %s
        """,
        (recipe_id,),
    ).fetchone()

    if recipe_row is None:
        raise ValueError(
            f"No recipe exists with ID {recipe_id}."
        )

    recipe_servings = float(recipe_row["servings"])

    if recipe_servings <= 0:
        raise ValueError(
            "Recipe servings must be greater than zero."
        )

    ingredients = connection.execute(
        """
        SELECT
            ri.ingredient_id,
            ri.quantity,
            ri.unit,
            i.ingredient_name
        FROM recipe_ingredients AS ri
        JOIN ingredients AS i
            ON ri.ingredient_id = i.ingredient_id
        WHERE ri.recipe_id = %s
        """,
        (recipe_id,),
    ).fetchall()

    warnings: list[str] = []

    for ingredient in ingredients:
        required_quantity = (
            float(ingredient["quantity"])
            * logged_servings
            / recipe_servings
        )

        pantry_item = connection.execute(
            """
            SELECT
                pantry_id,
                quantity_on_hand,
                unit
            FROM pantry_inventory
            WHERE ingredient_id = %s
            """,
            (ingredient["ingredient_id"],),
        ).fetchone()

        if pantry_item is None:
            warnings.append(
                f"{ingredient['ingredient_name']} was not "
                "found in the pantry."
            )
            continue

        if not can_convert_units(
            ingredient["unit"],
            pantry_item["unit"],
        ):
            warnings.append(
                f"{ingredient['ingredient_name']} was not "
                f"deducted because {ingredient['unit']} "
                f"cannot be converted to "
                f"{pantry_item['unit']}."
            )
            continue

        required_pantry_quantity = convert_quantity(
            quantity=required_quantity,
            from_unit=ingredient["unit"],
            to_unit=pantry_item["unit"],
        )

        quantity_on_hand = float(
            pantry_item["quantity_on_hand"]
        )

        actual_deduction = min(
            required_pantry_quantity,
            quantity_on_hand,
        )

        new_quantity = max(
            quantity_on_hand - actual_deduction,
            0,
        )

        connection.execute(
            """
            UPDATE pantry_inventory
            SET
                quantity_on_hand = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE pantry_id = %s
            """,
            (
                new_quantity,
                pantry_item["pantry_id"],
            ),
        )

        if actual_deduction > 0:
            connection.execute(
                """
                INSERT INTO pantry_transactions (
                    pantry_id,
                    ingredient_id,
                    meal_log_id,
                    transaction_type,
                    quantity_change,
                    unit,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pantry_item["pantry_id"],
                    ingredient["ingredient_id"],
                    meal_log_id,
                    "Meal deduction",
                    -actual_deduction,
                    pantry_item["unit"],
                    (
                        f"Automatic deduction for meal-log "
                        f"entry {meal_log_id}"
                    ),
                ),
            )

        if quantity_on_hand < required_pantry_quantity:
            shortage = (
                required_pantry_quantity
                - quantity_on_hand
            )

            warnings.append(
                f"{ingredient['ingredient_name']} was short "
                f"by {shortage:,.2f} "
                f"{pantry_item['unit']}. Pantry was reduced "
                "to zero."
            )

    return warnings

def restore_pantry_for_meal(
    connection: psycopg.Connection,
    meal_log_id: int,
) -> None:
    """
    Restore pantry quantities previously deducted for a meal.

    Restoration is based on the recorded deduction transactions,
    so it restores exactly what was originally removed.
    """
    deductions = connection.execute(
        """
        SELECT
            pantry_transaction_id,
            pantry_id,
            ingredient_id,
            quantity_change,
            unit
        FROM pantry_transactions
        WHERE
            meal_log_id = %s
            AND transaction_type = 'Meal deduction'
        """,
        (meal_log_id,),
    ).fetchall()

    for deduction in deductions:
        quantity_to_restore = abs(
            float(deduction["quantity_change"])
        )

        connection.execute(
            """
            UPDATE pantry_inventory
            SET
                quantity_on_hand =
                    quantity_on_hand + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE pantry_id = %s
            """,
            (
                quantity_to_restore,
                deduction["pantry_id"],
            ),
        )

        connection.execute(
            """
            INSERT INTO pantry_transactions (
                pantry_id,
                ingredient_id,
                meal_log_id,
                transaction_type,
                quantity_change,
                unit,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                deduction["pantry_id"],
                deduction["ingredient_id"],
                meal_log_id,
                "Meal restoration",
                quantity_to_restore,
                deduction["unit"],
                (
                    f"Automatic restoration after deleting "
                    f"meal-log entry {meal_log_id}"
                ),
            ),
        )