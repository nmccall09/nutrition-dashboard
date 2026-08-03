from datetime import date, timedelta
import psycopg

import streamlit as st

from services.meal_log_service import (
    add_meal_log,
    delete_meal_log,
    get_meal_log,
)
from services.recipe_service import get_all_recipes


MEAL_TYPES = [
    "Breakfast",
    "Lunch",
    "Dinner",
    "Snack",
]

def render_add_meal_form() -> None:
    st.subheader("Log a Meal")

    if "meal_log_success" in st.session_state:
        st.success(
            st.session_state.pop(
                "meal_log_success"
            )
        )

    if "meal_log_pantry_warnings" in st.session_state:
        pantry_warnings = st.session_state.pop(
            "meal_log_pantry_warnings"
        )

        for warning in pantry_warnings:
            st.warning(warning)

    recipes = get_all_recipes()

    if recipes.empty:
        st.info(
            "Add at least one recipe before logging meals."
        )
        return

    recipe_options = {
        (
            f"{row.recipe_name} "
            f"({row.calories_per_serving:,.0f} cal, "
            f"{row.protein_per_serving:,.0f}g protein)"
        ): int(row.recipe_id)
        for row in recipes.itertuples()
    }

    selected_recipe_label = st.selectbox(
        "Recipe",
        options=list(recipe_options.keys()),
        key="meal_log_recipe",
    )

    recipe_id = recipe_options[selected_recipe_label]

    notes_key = f"meal_log_notes_{recipe_id}"

    if st.session_state.pop(
        "reset_meal_log_notes",
        False,
    ):
        st.session_state[notes_key] = ""

    selected_recipe = recipes.loc[
        recipes["recipe_id"] == recipe_id
    ].iloc[0]

    default_meal_type = selected_recipe["meal_type"]

    meal_type_index = (
        MEAL_TYPES.index(default_meal_type)
        if default_meal_type in MEAL_TYPES
        else 0
    )

    left, middle, right = st.columns(3)

    with left:
        meal_date = st.date_input(
            "Date",
            value=date.today(),
            max_value=date.today(),
            key="meal_log_date",
        )

    with middle:
        meal_type = st.selectbox(
            "Meal",
            options=MEAL_TYPES,
            index=meal_type_index,
            key=f"meal_log_type_{recipe_id}",
        )

    with right:
        servings = st.number_input(
            "Servings eaten",
            min_value=0.25,
            value=1.0,
            step=0.25,
            key=f"meal_log_servings_{recipe_id}",
        )

    preview_calories = (
        float(selected_recipe["calories_per_serving"])
        * servings
    )

    preview_protein = (
        float(selected_recipe["protein_per_serving"])
        * servings
    )

    preview_cost = (
        float(
            selected_recipe["effective_cost_per_serving"]
            or 0
        )
        * servings
    )

    preview_columns = st.columns(3)

    preview_columns[0].metric(
        "Calories",
        f"{preview_calories:,.0f}",
        border=True,
    )

    preview_columns[1].metric(
        "Protein",
        f"{preview_protein:,.1f} g",
        border=True,
    )

    preview_columns[2].metric(
        "Estimated Cost",
        f"${preview_cost:,.2f}",
        border=True,
    )

    cost_source = (
        "ingredient calculation"
        if selected_recipe["ingredient_count"] > 0
        else "manual recipe estimate"
    )

    st.caption(
        f"Cost is based on the {cost_source}."
    )

    notes = st.text_area(
        "Notes",
        placeholder=(
            "Optional: sauce changes, portion notes, "
            "how filling it was..."
        ),
        key=notes_key,
    )
    if st.button(
        "Log meal",
        type="primary",
        width="stretch",
        key=f"log_meal_button_{recipe_id}",
    ):
        try:
            meal_log_id, pantry_warnings = add_meal_log(
                meal_date=meal_date,
                meal_type=meal_type,
                recipe_id=recipe_id,
                servings=servings,
                notes=notes,
            )

        except psycopg.Error as error:
            st.error(
                f"The meal could not be logged: {error}"
            )

        else:
            st.session_state["meal_log_success"] = (
                f"Meal logged successfully with ID "
                f"{meal_log_id}. Pantry inventory was updated."
            )

            st.session_state[
                "meal_log_pantry_warnings"
            ] = pantry_warnings

            st.session_state[
                "reset_meal_log_notes"
            ] = True

            st.rerun()

def render_meal_history() -> None:
    st.subheader("Meal History")

    default_start = date.today() - timedelta(days=6)

    left, right = st.columns(2)

    with left:
        start_date = st.date_input(
            "Start date",
            value=default_start,
            key="meal_history_start",
        )

    with right:
        end_date = st.date_input(
            "End date",
            value=date.today(),
            key="meal_history_end",
        )

    if start_date > end_date:
        st.error(
            "Start date cannot be after end date."
        )
        return

    meals = get_meal_log(
        start_date=start_date,
        end_date=end_date,
    )

    if meals.empty:
        st.info(
            "No meals were logged during this period."
        )
        return

    total_columns = st.columns(4)

    total_columns[0].metric(
        "Meals Logged",
        f"{len(meals)}",
        border=True,
    )

    total_columns[1].metric(
        "Calories",
        f"{meals['calories'].sum():,.0f}",
        border=True,
    )

    total_columns[2].metric(
        "Protein",
        f"{meals['protein'].sum():,.1f} g",
        border=True,
    )

    total_columns[3].metric(
        "Estimated Cost",
        f"${meals['estimated_cost'].sum():,.2f}",
        border=True,
    )

    display = meals[
        [
            "meal_log_id",
            "meal_date",
            "meal_type",
            "recipe_name",
            "servings",
            "calories",
            "protein",
            "carbs",
            "fat",
            "estimated_cost",
            "cost_source",
            "notes",
        ]
    ].copy()

    display = display.rename(
        columns={
            "meal_log_id": "ID",
            "meal_date": "Date",
            "meal_type": "Meal",
            "recipe_name": "Recipe",
            "servings": "Servings",
            "calories": "Calories",
            "protein": "Protein",
            "carbs": "Carbs",
            "fat": "Fat",
            "estimated_cost": "Cost",
            "cost_source": "Cost Source",
            "notes": "Notes",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Date": st.column_config.DateColumn(
                format="MM/DD/YYYY",
            ),
            "Calories": st.column_config.NumberColumn(
                format="%.0f",
            ),
            "Protein": st.column_config.NumberColumn(
                format="%.1f g",
            ),
            "Carbs": st.column_config.NumberColumn(
                format="%.1f g",
            ),
            "Fat": st.column_config.NumberColumn(
                format="%.1f g",
            ),
            "Cost": st.column_config.NumberColumn(
                format="$%.2f",
            ),
        },
    )

    render_delete_meal_section(meals)

def render_delete_meal_section(meals) -> None:
    with st.expander("Delete a meal entry"):
        meal_options = {
            (
                f"{row.meal_date.strftime('%m/%d/%Y')} — "
                f"{row.recipe_name} — "
                f"{row.servings:g} serving(s) — "
                f"ID {row.meal_log_id}"
            ): int(row.meal_log_id)
            for row in meals.itertuples()
        }

        selected_label = st.selectbox(
            "Meal entry",
            options=list(meal_options.keys()),
            key="delete_meal_selection",
        )

        confirmed = st.checkbox(
            "Confirm deletion",
            key="delete_meal_confirmation",
        )

        if st.button(
            "Delete meal entry",
            disabled=not confirmed,
            key="delete_meal_button",
        ):
            try:
                delete_meal_log(
                    meal_options[selected_label]
                )

            except (psycopg.Error, ValueError) as error:
                st.error(
                    f"The entry could not be deleted: "
                    f"{error}"
                )

            else:
                st.success("Meal entry deleted.")
                st.rerun()

def render() -> None:
    st.title("Meal Log")

    st.caption(
        "Record meals and automatically calculate calories, "
        "macros, and estimated cost."
    )

    log_tab, history_tab = st.tabs(
        [
            "Log Meal",
            "Meal History",
        ]
    )

    with log_tab:
        render_add_meal_form()

    with history_tab:
        render_meal_history()