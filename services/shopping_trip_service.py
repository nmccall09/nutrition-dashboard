from datetime import date
from typing import Any

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

def create_shopping_trip(
    trip_name: str,
    start_date: date,
    end_date: date,
    shopping_list: pd.DataFrame,
    notes: str = "",
) -> int:
    """
    Save a generated shopping list as a persistent trip.
    """
    purchasable_items = shopping_list.loc[
        shopping_list["purchase_quantity"] > 0
    ].copy()

    if purchasable_items.empty:
        raise ValueError(
            "There are no ingredients to purchase."
        )

    estimated_total = float(
        purchasable_items["checkout_cost"].sum()
    )

    with get_connection() as connection:
        try:
            trip_row = connection.execute(
                """
                INSERT INTO shopping_trips (
                    trip_name,
                    start_date,
                    end_date,
                    status,
                    estimated_checkout_cost,
                    actual_total_cost,
                    notes
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'Open',
                    %s,
                    0,
                    %s
                )
                RETURNING shopping_trip_id
                """,
                (
                    trip_name.strip(),
                    start_date,
                    end_date,
                    estimated_total,
                    notes.strip(),
                ),
            ).fetchone()

            if trip_row is None:
                raise RuntimeError(
                    "PostgreSQL did not return a "
                    "shopping-trip ID."
                )

            shopping_trip_id = int(
                trip_row["shopping_trip_id"]
            )

            item_rows = []

            for row in purchasable_items.itertuples():
                package_quantity = (
                    float(row.package_quantity)
                    if pd.notna(row.package_quantity)
                    else None
                )

                package_unit = (
                    str(row.package_unit)
                    if pd.notna(row.package_unit)
                    else None
                )

                packages_planned = int(
                    row.packages_needed
                    if pd.notna(row.packages_needed)
                    else 0
                )

                planned_purchase_quantity = (
                    float(row.purchased_quantity)
                    if pd.notna(row.purchased_quantity)
                    else float(row.purchase_quantity)
                )

                estimated_checkout_cost = (
                    float(row.checkout_cost)
                    if pd.notna(row.checkout_cost)
                    else 0.0
                )

                actual_unit = (
                    package_unit
                    if package_unit
                    else str(row.unit)
                )

                item_rows.append(
                    (
                        shopping_trip_id,
                        int(row.ingredient_id),
                        float(row.required_quantity),
                        float(row.purchase_quantity),
                        str(row.unit),
                        package_quantity,
                        package_unit,
                        packages_planned,
                        planned_purchase_quantity,
                        estimated_checkout_cost,
                        str(row.preferred_store),
                        actual_unit,
                        str(row.preferred_store),
                    )
                )

            insert_items_query = """
                INSERT INTO shopping_trip_items (
                    shopping_trip_id,
                    ingredient_id,
                    required_quantity,
                    need_to_buy_quantity,
                    need_unit,
                    package_quantity,
                    package_unit,
                    packages_planned,
                    planned_purchase_quantity,
                    estimated_checkout_cost,
                    preferred_store,
                    actual_unit,
                    actual_store
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
            """

            with connection.cursor() as cursor:
                cursor.executemany(
                    insert_items_query,
                    item_rows,
                )

            connection.commit()

            return shopping_trip_id

        except Exception:
            connection.rollback()
            raise


def get_shopping_trips() -> pd.DataFrame:
    """
    Return all saved shopping trips.
    """
    query = """
        SELECT
            st.shopping_trip_id,
            st.trip_name,
            st.start_date,
            st.end_date,
            st.status,
            st.estimated_checkout_cost,
            st.actual_total_cost,
            st.notes,
            st.created_at,
            st.completed_at,

            COUNT(sti.shopping_trip_item_id)
                AS item_count,

            COALESCE(
                SUM(sti.purchased),
                0
            ) AS purchased_count

        FROM shopping_trips AS st

        LEFT JOIN shopping_trip_items AS sti
            ON st.shopping_trip_id = sti.shopping_trip_id

        GROUP BY
            st.shopping_trip_id,
            st.trip_name,
            st.start_date,
            st.end_date,
            st.status,
            st.estimated_checkout_cost,
            st.actual_total_cost,
            st.notes,
            st.created_at,
            st.completed_at

        ORDER BY
            st.created_at DESC,
            st.shopping_trip_id DESC
    """

    result = query_dataframe(query)

    if not result.empty:
        result["start_date"] = pd.to_datetime(
            result["start_date"]
        )

        result["end_date"] = pd.to_datetime(
            result["end_date"]
        )

        result["created_at"] = pd.to_datetime(
            result["created_at"]
        )

        result["completed_at"] = pd.to_datetime(
            result["completed_at"],
            errors="coerce",
        )

    return result

def get_shopping_trip(
    shopping_trip_id: int,
) -> dict | None:
    """
    Return one shopping trip.
    """
    query = """
        SELECT *
        FROM shopping_trips
        WHERE shopping_trip_id = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (shopping_trip_id,),
        ).fetchone()

    return dict(row) if row else None


def get_shopping_trip_items(
    shopping_trip_id: int,
) -> pd.DataFrame:
    """
    Return all items belonging to one shopping trip.
    """
    query = """
        SELECT
            sti.shopping_trip_item_id,
            sti.shopping_trip_id,
            sti.ingredient_id,
            i.ingredient_name,
            i.category,

            sti.required_quantity,
            sti.need_to_buy_quantity,
            sti.need_unit,

            sti.package_quantity,
            sti.package_unit,
            sti.packages_planned,
            sti.planned_purchase_quantity,
            sti.estimated_checkout_cost,

            sti.preferred_store,
            sti.purchased,
            sti.actual_quantity,
            sti.actual_unit,
            sti.actual_price,
            sti.actual_store,
            sti.pantry_added

        FROM shopping_trip_items AS sti

        JOIN ingredients AS i
            ON sti.ingredient_id = i.ingredient_id

        WHERE sti.shopping_trip_id = %s

        ORDER BY
            CASE sti.preferred_store
                WHEN 'Costco' THEN 1
                WHEN 'Aldi' THEN 2
                ELSE 3
            END,
            i.category,
            i.ingredient_name
    """

    result = query_dataframe(
        query,
        (shopping_trip_id,),
    )

    if not result.empty:
        result["purchased"] = (
            result["purchased"].astype(bool)
        )

        result["pantry_added"] = (
            result["pantry_added"].astype(bool)
        )

    return result

def update_shopping_trip_items(
    edited_items: pd.DataFrame,
) -> None:
    """
    Save editable purchase fields and refresh the trip's
    actual total cost.
    """
    if edited_items.empty:
        return

    update_query = """
        UPDATE shopping_trip_items
        SET
            purchased = %s,
            actual_quantity = %s,
            actual_unit = %s,
            actual_price = %s,
            actual_store = %s
        WHERE shopping_trip_item_id = %s
    """

    rows = []

    for row in edited_items.itertuples():
        actual_quantity = (
            float(row.actual_quantity)
            if pd.notna(row.actual_quantity)
            else None
        )

        actual_price = (
            float(row.actual_price)
            if pd.notna(row.actual_price)
            else None
        )

        actual_unit = (
            str(row.actual_unit).strip()
            if pd.notna(row.actual_unit)
            else None
        )

        actual_store = (
            str(row.actual_store).strip()
            if pd.notna(row.actual_store)
            else None
        )

        rows.append(
            (
                int(bool(row.purchased)),
                actual_quantity,
                actual_unit,
                actual_price,
                actual_store,
                int(row.shopping_trip_item_id),
            )
        )

    shopping_trip_id = int(
        edited_items["shopping_trip_id"].iloc[0]
    )

    with get_connection() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.executemany(
                    update_query,
                    rows,
                )

            connection.execute(
                """
                UPDATE shopping_trips
                SET actual_total_cost = (
                    SELECT COALESCE(
                        SUM(
                            CASE
                                WHEN purchased = 1
                                    THEN COALESCE(
                                        actual_price,
                                        0
                                    )
                                ELSE 0
                            END
                        ),
                        0
                    )
                    FROM shopping_trip_items
                    WHERE shopping_trip_id = %s
                )
                WHERE shopping_trip_id = %s
                """,
                (
                    shopping_trip_id,
                    shopping_trip_id,
                ),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

def add_purchased_item_to_pantry(
    connection: psycopg.Connection,
    item: dict[str, Any],
) -> str | None:
    """
    Add one purchased shopping-trip item to pantry inventory.

    Returns a warning when the item cannot be added.
    """
    if not bool(item["purchased"]):
        return None

    if bool(item["pantry_added"]):
        return None

    actual_quantity = float(
        item["actual_quantity"] or 0
    )

    actual_unit = (
        str(item["actual_unit"]).strip()
        if item["actual_unit"]
        else None
    )

    if actual_quantity <= 0:
        return (
            f"{item['ingredient_name']} was purchased but "
            "has no actual quantity."
        )

    if not actual_unit:
        return (
            f"{item['ingredient_name']} was purchased but "
            "has no actual unit."
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
        (item["ingredient_id"],),
    ).fetchone()

    if pantry_item is None:
        pantry_row = connection.execute(
            """
            INSERT INTO pantry_inventory (
                ingredient_id,
                quantity_on_hand,
                unit,
                minimum_quantity,
                expiration_date,
                notes,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                0,
                NULL,
                %s,
                CURRENT_TIMESTAMP
            )
            RETURNING pantry_id
            """,
            (
                item["ingredient_id"],
                actual_quantity,
                actual_unit,
                (
                    f"Added from shopping trip "
                    f"{item['shopping_trip_id']}"
                ),
            ),
        ).fetchone()

        if pantry_row is None:
            raise RuntimeError(
                "PostgreSQL did not return a pantry ID."
            )

        pantry_id = int(
            pantry_row["pantry_id"]
        )

        transaction_quantity = actual_quantity
        transaction_unit = actual_unit

    else:
        pantry_unit = str(
            pantry_item["unit"]
        )

        if not can_convert_units(
            actual_unit,
            pantry_unit,
        ):
            return (
                f"{item['ingredient_name']} was not added "
                f"because {actual_unit} cannot be converted "
                f"to {pantry_unit}."
            )

        converted_quantity = convert_quantity(
            quantity=actual_quantity,
            from_unit=actual_unit,
            to_unit=pantry_unit,
        )

        pantry_id = int(
            pantry_item["pantry_id"]
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
                converted_quantity,
                pantry_id,
            ),
        )

        transaction_quantity = converted_quantity
        transaction_unit = pantry_unit

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
        VALUES (
            %s,
            %s,
            NULL,
            'Purchase',
            %s,
            %s,
            %s
        )
        """,
        (
            pantry_id,
            item["ingredient_id"],
            transaction_quantity,
            transaction_unit,
            (
                f"Purchase from shopping trip "
                f"{item['shopping_trip_id']}"
            ),
        ),
    )

    connection.execute(
        """
        UPDATE shopping_trip_items
        SET pantry_added = 1
        WHERE shopping_trip_item_id = %s
        """,
        (
            item["shopping_trip_item_id"],
        ),
    )

    return None

def complete_shopping_trip(
    shopping_trip_id: int,
) -> list[str]:
    """
    Complete a trip and add purchased quantities to pantry.

    Returns warnings for items that could not be added.
    """
    with get_connection() as connection:
        try:
            trip = connection.execute(
                """
                SELECT status
                FROM shopping_trips
                WHERE shopping_trip_id = %s
                """,
                (shopping_trip_id,),
            ).fetchone()

            if trip is None:
                raise ValueError(
                    "The shopping trip was not found."
                )

            if trip["status"] == "Completed":
                raise ValueError(
                    "This shopping trip is already completed."
                )

            items = connection.execute(
                """
                SELECT
                    sti.*,
                    i.ingredient_name

                FROM shopping_trip_items AS sti

                JOIN ingredients AS i
                    ON sti.ingredient_id = i.ingredient_id

                WHERE sti.shopping_trip_id = %s
                """,
                (shopping_trip_id,),
            ).fetchall()

            warnings: list[str] = []

            for item in items:
                warning = add_purchased_item_to_pantry(
                    connection,
                    item,
                )

                if warning:
                    warnings.append(warning)

            actual_total = sum(
                float(item["actual_price"] or 0)
                for item in items
                if item["purchased"]
            )

            connection.execute(
                """
                UPDATE shopping_trips
                SET
                    status = 'Completed',
                    actual_total_cost = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE shopping_trip_id = %s
                """,
                (
                    actual_total,
                    shopping_trip_id,
                ),
            )

            connection.commit()

            return warnings

        except Exception:
            connection.rollback()
            raise


def delete_shopping_trip(
    shopping_trip_id: int,
) -> None:
    """
    Delete an open shopping trip.
    """
    with get_connection() as connection:
        trip = connection.execute(
            """
            SELECT status
            FROM shopping_trips
            WHERE shopping_trip_id = %s
            """,
            (shopping_trip_id,),
        ).fetchone()

        if trip is None:
            raise ValueError(
                "The shopping trip was not found."
            )

        if trip["status"] == "Completed":
            raise ValueError(
                "Completed trips cannot be deleted because "
                "they may have already updated pantry inventory."
            )

        connection.execute(
            """
            DELETE FROM shopping_trips
            WHERE shopping_trip_id = %s
            """,
            (shopping_trip_id,),
        )

        connection.commit()