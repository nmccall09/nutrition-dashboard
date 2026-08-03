from datetime import date, timedelta
import psycopg

import pandas as pd
import streamlit as st

from services.ingredient_service import (
    get_all_ingredients,
)
from services.pantry_service import (
    delete_pantry_item,
    get_pantry_inventory,
    get_pantry_item,
    upsert_pantry_item,
)


UNITS = [
    "oz",
    "lb",
    "g",
    "kg",
    "cup",
    "tbsp",
    "tsp",
    "each",
    "can",
    "bag",
    "container",
]


def render_inventory_form() -> None:
    st.subheader("Add or Update Pantry Item")

    ingredients = get_all_ingredients()

    if ingredients.empty:
        st.info(
            "Add ingredients before creating pantry inventory."
        )
        return

    ingredient_options = {
        row.ingredient_name: int(row.ingredient_id)
        for row in ingredients.itertuples()
    }

    selected_name = st.selectbox(
        "Ingredient",
        options=list(ingredient_options.keys()),
        key="pantry_ingredient",
    )

    ingredient_id = ingredient_options[selected_name]

    ingredient_row = ingredients.loc[
        ingredients["ingredient_id"] == ingredient_id
    ].iloc[0]

    existing_item = get_pantry_item(ingredient_id)

    default_unit = (
        existing_item["unit"]
        if existing_item is not None
        else str(ingredient_row["default_unit"])
    )

    unit_index = (
        UNITS.index(default_unit)
        if default_unit in UNITS
        else 0
    )

    existing_expiration = None

    if (
        existing_item is not None
        and existing_item["expiration_date"]
    ):
        existing_expiration = date.fromisoformat(
            existing_item["expiration_date"]
        )

    with st.form(
        key=f"pantry_form_{ingredient_id}",
    ):
        left, middle, right = st.columns(3)

        with left:
            quantity_on_hand = st.number_input(
                "Quantity on hand",
                min_value=0.0,
                value=float(
                    existing_item["quantity_on_hand"]
                    if existing_item
                    else 0
                ),
                step=0.25,
            )

        with middle:
            unit = st.selectbox(
                "Unit",
                options=UNITS,
                index=unit_index,
            )

        with right:
            minimum_quantity = st.number_input(
                "Minimum desired quantity",
                min_value=0.0,
                value=float(
                    existing_item["minimum_quantity"]
                    if existing_item
                    else 0
                ),
                step=0.25,
                help=(
                    "Items at or below this amount will be "
                    "marked as low stock."
                ),
            )

        track_expiration = st.checkbox(
            "Track expiration date",
            value=existing_expiration is not None,
        )

        expiration_date = None

        if track_expiration:
            expiration_date = st.date_input(
                "Expiration date",
                value=(
                    existing_expiration
                    or date.today() + timedelta(days=7)
                ),
                format="MM/DD/YYYY",
                width="stretch",
            )

        notes = st.text_area(
            "Notes",
            value=(
                existing_item["notes"]
                if existing_item
                and existing_item["notes"]
                else ""
            ),
            placeholder=(
                "Opened, frozen, second package in freezer..."
            ),
        )

        submitted = st.form_submit_button(
            "Save pantry item",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    try:
        upsert_pantry_item(
            ingredient_id=ingredient_id,
            quantity_on_hand=quantity_on_hand,
            unit=unit,
            minimum_quantity=minimum_quantity,
            expiration_date=expiration_date,
            notes=notes,
        )

    except psycopg.Error as error:
        st.error(
            f"The pantry item could not be saved: {error}"
        )

    else:
        st.success("Pantry item saved.")
        st.rerun()


def prepare_inventory_display(
    inventory: pd.DataFrame,
) -> pd.DataFrame:
    display = inventory.copy()

    today = pd.Timestamp(date.today())
    warning_date = today + pd.Timedelta(days=3)

    display["Stock Status"] = display.apply(
        lambda row: (
            "Low stock"
            if row["quantity_on_hand"]
            <= row["minimum_quantity"]
            else "In stock"
        ),
        axis=1,
    )

    display["Expiration Status"] = display[
        "expiration_date"
    ].apply(
        lambda expiration: (
            "Not tracked"
            if pd.isna(expiration)
            else (
                "Expired"
                if expiration.normalize() < today
                else (
                    "Expiring soon"
                    if expiration.normalize()
                    <= warning_date
                    else "Fresh"
                )
            )
        )
    )

    return display[
        [
            "pantry_id",
            "ingredient_name",
            "category",
            "quantity_on_hand",
            "unit",
            "minimum_quantity",
            "Stock Status",
            "expiration_date",
            "Expiration Status",
            "notes",
        ]
    ].rename(
        columns={
            "pantry_id": "ID",
            "ingredient_name": "Ingredient",
            "category": "Category",
            "quantity_on_hand": "On Hand",
            "unit": "Unit",
            "minimum_quantity": "Minimum",
            "expiration_date": "Expiration",
            "notes": "Notes",
        }
    )


def render_inventory_table() -> None:
    st.subheader("Current Inventory")

    inventory = get_pantry_inventory()

    if inventory.empty:
        st.info(
            "Your pantry inventory is currently empty."
        )
        return

    display = prepare_inventory_display(inventory)

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "ID": None,
            "On Hand": st.column_config.NumberColumn(
                format="%,.2f",
            ),
            "Minimum": st.column_config.NumberColumn(
                format="%,.2f",
            ),
            "Expiration": st.column_config.DateColumn(
                format="MM/DD/YYYY",
            ),
        },
    )

    low_stock_count = int(
        (
            inventory["quantity_on_hand"]
            <= inventory["minimum_quantity"]
        ).sum()
    )

    expiring_soon_count = int(
        inventory["expiration_date"]
        .between(
            pd.Timestamp(date.today()),
            pd.Timestamp(date.today() + timedelta(days=3)),
            inclusive="both",
        )
        .sum()
    )

    expired_count = int(
        (
            inventory["expiration_date"]
            < pd.Timestamp(date.today())
        ).sum()
    )

    metrics = st.columns(3)

    metrics[0].metric(
        "Low Stock",
        f"{low_stock_count:,}",
        border=True,
    )

    metrics[1].metric(
        "Expiring Soon",
        f"{expiring_soon_count:,}",
        border=True,
    )

    metrics[2].metric(
        "Expired",
        f"{expired_count:,}",
        border=True,
    )

    render_delete_pantry_item(inventory)


def render_delete_pantry_item(
    inventory: pd.DataFrame,
) -> None:
    with st.expander("Remove pantry item"):
        options = {
            (
                f"{row.ingredient_name} — "
                f"{row.quantity_on_hand:g} {row.unit}"
            ): int(row.pantry_id)
            for row in inventory.itertuples()
        }

        selected_label = st.selectbox(
            "Pantry item",
            options=list(options.keys()),
            key="delete_pantry_selection",
        )

        confirmed = st.checkbox(
            "Confirm removal",
            key="delete_pantry_confirmation",
        )

        if st.button(
            "Remove pantry item",
            disabled=not confirmed,
            key="delete_pantry_button",
        ):
            try:
                delete_pantry_item(
                    options[selected_label]
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The pantry item could not be removed: "
                    f"{error}"
                )

            else:
                st.success("Pantry item removed.")
                st.rerun()


def render() -> None:
    st.title("Pantry Inventory")

    st.caption(
        "Track ingredients already available and deduct them "
        "from generated grocery requirements."
    )

    add_tab, inventory_tab = st.tabs(
        [
            "Add or Update",
            "View Inventory",
        ]
    )

    with add_tab:
        render_inventory_form()

    with inventory_tab:
        render_inventory_table()