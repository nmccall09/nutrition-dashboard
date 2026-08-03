import psycopg

import pandas as pd
import streamlit as st

from services.shopping_trip_service import (
    complete_shopping_trip,
    delete_shopping_trip,
    get_shopping_trip,
    get_shopping_trip_items,
    get_shopping_trips,
    update_shopping_trip_items,
)


STORE_OPTIONS = [
    "Costco",
    "Aldi",
    "Other",
]


UNIT_OPTIONS = [
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


def render_trip_history(
    trips: pd.DataFrame,
) -> None:
    st.subheader("Shopping-Trip History")

    if trips.empty:
        st.info("No shopping trips have been saved yet.")
        return

    display = trips[
        [
            "shopping_trip_id",
            "trip_name",
            "start_date",
            "end_date",
            "status",
            "item_count",
            "purchased_count",
            "estimated_checkout_cost",
            "actual_total_cost",
            "created_at",
            "completed_at",
        ]
    ].copy()

    display = display.rename(
        columns={
            "shopping_trip_id": "ID",
            "trip_name": "Trip",
            "start_date": "Plan Start",
            "end_date": "Plan End",
            "status": "Status",
            "item_count": "Items",
            "purchased_count": "Purchased",
            "estimated_checkout_cost": "Estimated",
            "actual_total_cost": "Actual",
            "created_at": "Created",
            "completed_at": "Completed",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Plan Start": st.column_config.DateColumn(
                format="MM/DD/YYYY",
            ),
            "Plan End": st.column_config.DateColumn(
                format="MM/DD/YYYY",
            ),
            "Created": st.column_config.DatetimeColumn(
                format="MM/DD/YYYY h:mm a",
            ),
            "Completed": st.column_config.DatetimeColumn(
                format="MM/DD/YYYY h:mm a",
            ),
            "Items": st.column_config.NumberColumn(
                format="%,d",
            ),
            "Purchased": st.column_config.NumberColumn(
                format="%,d",
            ),
            "Estimated": st.column_config.NumberColumn(
                format="$%,.2f",
            ),
            "Actual": st.column_config.NumberColumn(
                format="$%,.2f",
            ),
        },
    )


def render_trip_editor(
    shopping_trip_id: int,
) -> None:
    trip = get_shopping_trip(shopping_trip_id)
    items = get_shopping_trip_items(
        shopping_trip_id
    )

    if trip is None:
        st.error("The selected shopping trip was not found.")
        return

    st.subheader(trip["trip_name"])

    estimated_total = float(
        trip["estimated_checkout_cost"] or 0
    )

    actual_total = float(
        items.loc[
            items["purchased"],
            "actual_price",
        ].fillna(0).sum()
    )

    difference = actual_total - estimated_total

    metrics = st.columns(4)

    metrics[0].metric(
        "Status",
        trip["status"],
        border=True,
    )

    metrics[1].metric(
        "Estimated",
        f"${estimated_total:,.2f}",
        border=True,
    )

    metrics[2].metric(
        "Actual",
        f"${actual_total:,.2f}",
        border=True,
    )

    metrics[3].metric(
        "Difference",
        f"${difference:,.2f}",
        delta=(
            "Over estimate"
            if difference > 0
            else "Under estimate"
        ),
        delta_color=(
            "inverse"
            if difference > 0
            else "normal"
        ),
        border=True,
    )

    if items.empty:
        st.info("This trip contains no items.")
        return

    if trip["status"] == "Completed":
        st.info(
            "This trip is completed and can no longer be edited."
        )

        render_read_only_items(items)
        return

    editable = items[
        [
            "shopping_trip_item_id",
            "shopping_trip_id",
            "ingredient_name",
            "need_to_buy_quantity",
            "need_unit",
            "packages_planned",
            "planned_purchase_quantity",
            "estimated_checkout_cost",
            "preferred_store",
            "purchased",
            "actual_quantity",
            "actual_unit",
            "actual_price",
            "actual_store",
        ]
    ].copy()

    edited = st.data_editor(
        editable,
        hide_index=True,
        width="stretch",
        key=f"shopping_trip_editor_{shopping_trip_id}",
        disabled=[
            "shopping_trip_item_id",
            "shopping_trip_id",
            "ingredient_name",
            "need_to_buy_quantity",
            "need_unit",
            "packages_planned",
            "planned_purchase_quantity",
            "estimated_checkout_cost",
            "preferred_store",
        ],
        column_config={
            "shopping_trip_item_id": None,
            "shopping_trip_id": None,
            "ingredient_name": "Ingredient",
            "need_to_buy_quantity": (
                st.column_config.NumberColumn(
                    "Need to Buy",
                    format="%,.2f",
                )
            ),
            "need_unit": "Need Unit",
            "packages_planned": (
                st.column_config.NumberColumn(
                    "Packages",
                    format="%,d",
                )
            ),
            "planned_purchase_quantity": (
                st.column_config.NumberColumn(
                    "Planned Quantity",
                    format="%,.2f",
                )
            ),
            "estimated_checkout_cost": (
                st.column_config.NumberColumn(
                    "Estimated Cost",
                    format="$%,.2f",
                )
            ),
            "preferred_store": "Planned Store",
            "purchased": st.column_config.CheckboxColumn(
                "Purchased"
            ),
            "actual_quantity": (
                st.column_config.NumberColumn(
                    "Actual Quantity",
                    min_value=0.0,
                    format="%,.2f",
                )
            ),
            "actual_unit": st.column_config.SelectboxColumn(
                "Actual Unit",
                options=UNIT_OPTIONS,
            ),
            "actual_price": (
                st.column_config.NumberColumn(
                    "Actual Price",
                    min_value=0.0,
                    format="$%,.2f",
                )
            ),
            "actual_store": (
                st.column_config.SelectboxColumn(
                    "Actual Store",
                    options=STORE_OPTIONS,
                )
            ),
        },
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "Save purchase updates",
            type="primary",
            width="stretch",
            key=f"save_trip_{shopping_trip_id}",
        ):
            try:
                update_shopping_trip_items(edited)

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The trip could not be updated: {error}"
                )

            else:
                st.success("Purchase updates saved.")
                st.rerun()

    with right:
        purchased_count = int(
            edited["purchased"].sum()
        )

        if st.button(
            "Complete trip and restock pantry",
            width="stretch",
            disabled=purchased_count == 0,
            key=f"complete_trip_{shopping_trip_id}",
        ):
            try:
                update_shopping_trip_items(edited)

                warnings = complete_shopping_trip(
                    shopping_trip_id
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The trip could not be completed: {error}"
                )

            else:
                st.success(
                    "Shopping trip completed and purchased "
                    "items were added to the pantry."
                )

                for warning in warnings:
                    st.warning(warning)

                st.rerun()

    with st.expander("Delete open trip"):
        confirmed = st.checkbox(
            "Confirm trip deletion",
            key=f"confirm_delete_trip_{shopping_trip_id}",
        )

        if st.button(
            "Delete shopping trip",
            disabled=not confirmed,
            key=f"delete_trip_{shopping_trip_id}",
        ):
            try:
                delete_shopping_trip(
                    shopping_trip_id
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The trip could not be deleted: {error}"
                )

            else:
                st.success("Shopping trip deleted.")
                st.rerun()


def render_read_only_items(
    items: pd.DataFrame,
) -> None:
    display = items[
        [
            "ingredient_name",
            "purchased",
            "actual_quantity",
            "actual_unit",
            "actual_price",
            "actual_store",
            "pantry_added",
        ]
    ].copy()

    display = display.rename(
        columns={
            "ingredient_name": "Ingredient",
            "purchased": "Purchased",
            "actual_quantity": "Actual Quantity",
            "actual_unit": "Unit",
            "actual_price": "Actual Price",
            "actual_store": "Store",
            "pantry_added": "Added to Pantry",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Purchased": st.column_config.CheckboxColumn(),
            "Added to Pantry": (
                st.column_config.CheckboxColumn()
            ),
            "Actual Quantity": (
                st.column_config.NumberColumn(
                    format="%,.2f",
                )
            ),
            "Actual Price": (
                st.column_config.NumberColumn(
                    format="$%,.2f",
                )
            ),
        },
    )


def render() -> None:
    st.title("Shopping Trips")

    st.caption(
        "Track grocery purchases, actual spending, and "
        "pantry restocking."
    )

    trips = get_shopping_trips()

    history_tab, manage_tab = st.tabs(
        [
            "Trip History",
            "Manage Trip",
        ]
    )

    with history_tab:
        render_trip_history(trips)

    with manage_tab:
        if trips.empty:
            st.info(
                "Save a generated shopping list to create "
                "your first trip."
            )
            return

        trip_options = {
            (
                f"{row.trip_name} — "
                f"{row.status} — "
                f"ID {row.shopping_trip_id}"
            ): int(row.shopping_trip_id)
            for row in trips.itertuples()
        }

        selected_label = st.selectbox(
            "Shopping trip",
            options=list(trip_options.keys()),
            key="shopping_trip_selection",
        )

        render_trip_editor(
            trip_options[selected_label]
        )