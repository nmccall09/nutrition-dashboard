from datetime import date, timedelta

import streamlit as st
import psycopg

from services.shopping_service import (
    get_generated_shopping_list,
)

from services.shopping_trip_service import (
    create_shopping_trip,
)


def get_current_week() -> tuple[date, date]:
    today = date.today()

    monday = today - timedelta(
        days=today.weekday()
    )

    return monday, monday + timedelta(days=6)


def render() -> None:
    st.title("Generated Shopping List")

    st.caption(
        "Ingredients are combined from the selected week's "
        "meal plan and separated by preferred store."
    )

    default_start, _ = get_current_week()

    week_start = st.date_input(
        "Week starting",
        value=default_start,
        format="MM/DD/YYYY",
        width="stretch",
        key="shopping_week_start",
    )

    week_end = week_start + timedelta(days=6)

    shopping_list = get_generated_shopping_list(
        start_date=week_start,
        end_date=week_end,
    )

    show_covered_items = st.checkbox(
        "Show items fully covered by pantry",
        value=True,
    )

    if not show_covered_items:
        shopping_list = shopping_list.loc[
            shopping_list["purchase_quantity"] > 0
        ].copy()

    if shopping_list.empty:
        st.info(
            "No shopping items were generated. Add planned "
            "meals with assigned recipe ingredients first."
        )
        return

    estimated_usage_cost = float(
        shopping_list["estimated_cost"].sum()
    )

    estimated_checkout_cost = float(
        shopping_list["checkout_cost"].sum()
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Unique Ingredients",
        f"{len(shopping_list):,}",
        border=True,
    )

    metric_columns[1].metric(
        "Items to Purchase",
        f"{int((shopping_list['purchase_quantity'] > 0).sum()):,}",
        border=True,
    )

    metric_columns[2].metric(
        "Estimated Usage Cost",
        f"${estimated_usage_cost:,.2f}",
        border=True,
    )

    metric_columns[3].metric(
        "Estimated Checkout Cost",
        f"${estimated_checkout_cost:,.2f}",
        border=True,
    )

    for store in ["Costco", "Aldi", "Other"]:
        store_items = shopping_list.loc[
            shopping_list["preferred_store"] == store
        ].copy()

        if store_items.empty:
            continue

        st.subheader(store)

        store_cost = float(
            store_items["estimated_cost"].sum()
        )

        st.caption(
            f"Estimated subtotal: ${store_cost:,.2f}"
        )

        display = store_items[
            [
                "ingredient_name",
                "category",
                "required_quantity",
                "pantry_quantity",
                "purchase_quantity",
                "unit",
                "package_quantity",
                "package_unit",
                "package_size_in_need_unit",
                "packages_needed",
                "purchased_quantity",
                "expected_leftover",
                "estimated_cost",
                "checkout_cost",
                "package_description",
                "pantry_status",
                "package_status",
            ]
        ].copy()

        display = display.rename(
            columns={
                "ingredient_name": "Ingredient",
                "category": "Category",
                "required_quantity": "Required",
                "pantry_quantity": "In Pantry",
                "purchase_quantity": "Need to Buy",
                "unit": "Need Unit",
                "package_quantity": "Package Size",
                "package_unit": "Package Unit",
                "package_size_in_need_unit": "Converted Package Size",
                "packages_needed": "Packages",
                "purchased_quantity": "Purchase Quantity",
                "expected_leftover": "Expected Leftover",
                "estimated_cost": "Usage Cost",
                "checkout_cost": "Checkout Cost",
                "package_description": "Package",
                "pantry_status": "Pantry Status",
                "package_status": "Package Status",
            }
        )   
        
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            column_config={
                "Required": st.column_config.NumberColumn(
                    format="%,.2f",
                ),
                "In Pantry": st.column_config.NumberColumn(
                    format="%,.2f",
                ),
                "Need to Buy": st.column_config.NumberColumn(
                    format="%,.2f",
                ),
                "Package Size": st.column_config.NumberColumn(
                    format="%,.2f",
                ),
                "Converted Package Size": (
                    st.column_config.NumberColumn(
                        format="%,.2f",
                    )
                ),
                "Packages": st.column_config.NumberColumn(
                    format="%,d",
                ),
                "Purchase Quantity": (
                    st.column_config.NumberColumn(
                        format="%,.2f",
                    )
                ),
                "Expected Leftover": (
                    st.column_config.NumberColumn(
                        format="%,.2f",
                    )
                ),
                "Usage Cost": st.column_config.NumberColumn(
                    format="$%,.2f",
                ),
                "Checkout Cost": (
                    st.column_config.NumberColumn(
                        format="$%,.2f",
                    )
                ),
            },
        )

    # This section is outside the store loop.
    st.divider()
    st.subheader("Save Shopping Trip")

    purchasable_items = shopping_list.loc[
        shopping_list["purchase_quantity"] > 0
    ].copy()

    if purchasable_items.empty:
        st.info(
            "Every ingredient is covered by your pantry, "
            "so there is nothing to save as a shopping trip."
        )
        return

    default_trip_name = (
        f"Groceries "
        f"{week_start.strftime('%m/%d')}–"
        f"{week_end.strftime('%m/%d')}"
    )

    trip_name = st.text_input(
        "Trip name",
        value=default_trip_name,
        key="new_shopping_trip_name",
    )

    trip_notes = st.text_area(
        "Trip notes",
        placeholder="Optional notes for this grocery run",
        key="new_shopping_trip_notes",
    )

    if st.button(
        "Save as shopping trip",
        type="primary",
        width="stretch",
        key="save_generated_shopping_trip",
    ):
        try:
            shopping_trip_id = create_shopping_trip(
                trip_name=trip_name,
                start_date=week_start,
                end_date=week_end,
                shopping_list=purchasable_items,
                notes=trip_notes,
            )

        except (
            psycopg.Error,
            ValueError,
        ) as error:
            st.error(
                f"The shopping trip could not be saved: "
                f"{error}"
            )

        else:
            st.success(
                f"Shopping trip {shopping_trip_id} "
                "was created."
            )