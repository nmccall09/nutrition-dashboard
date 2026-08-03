from datetime import date, timedelta
import psycopg

import pandas as pd
import streamlit as st

from services.meal_plan_service import (
    add_meal_plan_entry,
    clear_meal_plan,
    delete_meal_plan_entry,
    get_meal_plan,
    log_planned_meal,
    log_planned_meals_for_date,
)
from services.recipe_service import get_all_recipes


MEAL_TYPES = [
    "Breakfast",
    "Lunch",
    "Dinner",
    "Snack",
]


def get_current_week() -> tuple[date, date]:
    """
    Return Monday and Sunday for the current week.
    """
    today = date.today()

    monday = today - timedelta(
        days=today.weekday()
    )

    sunday = monday + timedelta(days=6)

    return monday, sunday

def render_add_planned_meal(
    week_start: date,
    week_end: date,
) -> None:
    st.subheader("Add Planned Meal")

    if "planned_meal_success" in st.session_state:
        st.success(
            st.session_state.pop(
                "planned_meal_success"
            )
        )

    recipes = get_all_recipes()

    if recipes.empty:
        st.info(
            "Add at least one recipe before planning meals."
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
        key="planner_recipe",
    )

    recipe_id = recipe_options[selected_recipe_label]

    notes_key = f"planned_meal_notes_{recipe_id}"

    if st.session_state.pop(
        "reset_planned_meal_notes",
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
        plan_date = st.date_input(
            "Date",
            value=week_start,
            min_value=week_start,
            max_value=week_end,
            format="MM/DD/YYYY",
            width="stretch",
            key="planned_meal_date",
        )

    with middle:
        meal_type = st.selectbox(
            "Meal",
            options=MEAL_TYPES,
            index=meal_type_index,
            width="stretch",
            key=f"planned_meal_type_{recipe_id}",
        )

    with right:
        servings = st.number_input(
            "Servings planned",
            min_value=0.25,
            value=1.0,
            step=0.25,
            key=f"planned_servings_{recipe_id}",
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
        "Cost",
        f"${preview_cost:,.2f}",
        border=True,
    )

    notes = st.text_area(
        "Notes",
        placeholder="Optional preparation or serving notes",
        key=notes_key,
    )

    if st.button(
        "Add to meal plan",
        type="primary",
        width="stretch",
        key=f"add_planned_meal_{recipe_id}",
    ):
        try:
            add_meal_plan_entry(
                plan_date=plan_date,
                meal_type=meal_type,
                recipe_id=recipe_id,
                servings=servings,
                notes=notes,
            )

        except psycopg.Error as error:
            st.error(
                f"The planned meal could not be saved: {error}"
            )

        else:
            st.session_state["planned_meal_success"] = (
                "Meal added to the plan."
            )

            st.session_state[
                "reset_planned_meal_notes"
            ] = True

            st.rerun()

def render_week_summary(
    meal_plan: pd.DataFrame,
) -> None:
    if meal_plan.empty:
        return

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Planned Meals",
        f"{len(meal_plan)}",
        border=True,
    )

    metric_columns[1].metric(
        "Calories",
        f"{meal_plan['calories'].sum():,.0f}",
        border=True,
    )

    metric_columns[2].metric(
        "Protein",
        f"{meal_plan['protein'].sum():,.1f} g",
        border=True,
    )

    metric_columns[3].metric(
        "Estimated Cost",
        f"${meal_plan['estimated_cost'].sum():,.2f}",
        border=True,
    )


def render_plan_table(
    meal_plan: pd.DataFrame,
) -> None:
    st.subheader("Weekly Plan")

    if meal_plan.empty:
        st.info(
            "No meals have been planned for this week."
        )
        return

    display = meal_plan[
        [
            "meal_plan_id",
            "plan_date",
            "meal_type",
            "recipe_name",
            "servings",
            "calories",
            "protein",
            "estimated_cost",
            "is_logged",
            "notes",
        ]
    ].copy()

    display["is_logged"] = display[
        "is_logged"
    ].map(
        {
            0: "Not logged",
            1: "Logged",
        }
    )

    display = display.rename(
        columns={
            "meal_plan_id": "ID",
            "plan_date": "Date",
            "meal_type": "Meal",
            "recipe_name": "Recipe",
            "servings": "Servings",
            "calories": "Calories",
            "protein": "Protein",
            "estimated_cost": "Cost",
            "is_logged": "Status",
            "notes": "Notes",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "ID": None,
            "Date": st.column_config.DateColumn(
                format="ddd MM/DD",
            ),
            "Calories": st.column_config.NumberColumn(
                format="%.0f",
            ),
            "Protein": st.column_config.NumberColumn(
                format="%.1f g",
            ),
            "Cost": st.column_config.NumberColumn(
                format="$%.2f",
            ),
        },
    )


def render_delete_section(
    meal_plan: pd.DataFrame,
) -> None:
    if meal_plan.empty:
        return

    with st.expander("Delete a planned meal"):
        options = {
            (
                f"{row.plan_date.strftime('%m/%d')} — "
                f"{row.recipe_name} — "
                f"{row.servings:g} serving(s)"
            ): int(row.meal_plan_id)
            for row in meal_plan.itertuples()
        }

        selected_label = st.selectbox(
            "Planned meal",
            options=list(options.keys()),
            key="delete_plan_selection",
        )

        confirmed = st.checkbox(
            "Confirm deletion",
            key="delete_plan_confirmation",
        )

        if st.button(
            "Delete planned meal",
            disabled=not confirmed,
        ):
            try:
                delete_meal_plan_entry(
                    options[selected_label]
                )

            except (psycopg.Error, ValueError) as error:
                st.error(
                    f"The meal could not be deleted: {error}"
                )

            else:
                st.success("Planned meal deleted.")
                st.rerun()


def render_clear_week(
    week_start: date,
    week_end: date,
    meal_plan: pd.DataFrame,
) -> None:
    if meal_plan.empty:
        return

    with st.expander("Clear the entire week"):
        confirmed = st.checkbox(
            "Delete every planned meal in this week",
            key="clear_week_confirmation",
        )

        if st.button(
            "Clear weekly meal plan",
            disabled=not confirmed,
            type="secondary",
        ):
            clear_meal_plan(
                start_date=week_start,
                end_date=week_end,
            )

            st.success("Weekly meal plan cleared.")
            st.rerun()

def render_log_planned_meals(
    meal_plan: pd.DataFrame,
) -> None:
    """
    Log individual planned meals or all meals on one date.
    """
    if meal_plan.empty:
        return

    st.subheader("Log Planned Meals")

    unlogged = meal_plan.loc[
        meal_plan["is_logged"] == 0
    ].copy()

    if unlogged.empty:
        st.success(
            "Every planned meal in this week has been logged."
        )
        return

    single_tab, daily_tab = st.tabs(
        [
            "Log One Meal",
            "Log All for a Day",
        ]
    )

    with single_tab:
        meal_options = {
            (
                f"{row.plan_date.strftime('%a %m/%d')} — "
                f"{row.meal_type} — "
                f"{row.recipe_name} — "
                f"{row.servings:g} serving(s)"
            ): int(row.meal_plan_id)
            for row in unlogged.itertuples()
        }

        selected_label = st.selectbox(
            "Planned meal",
            options=list(meal_options.keys()),
            key="planned_meal_to_log",
        )

        if st.button(
            "Log selected planned meal",
            type="primary",
            width="stretch",
            key="log_selected_planned_meal",
        ):
            try:
                meal_log_id, pantry_warnings = log_planned_meal(
                    meal_options[selected_label]
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The meal could not be logged: {error}"
                )

            else:
                st.success(
                    f"Meal logged with ID {meal_log_id}."
                )
                for warning in pantry_warnings:
                    st.warning(warning)

                st.rerun()

    with daily_tab:
        available_dates = sorted(
            unlogged["plan_date"]
            .dt.date
            .unique()
            .tolist()
        )

        selected_date = st.selectbox(
            "Date",
            options=available_dates,
            format_func=lambda value: (
                value.strftime("%A, %B %d")
            ),
            key="planned_day_to_log",
        )

        meals_on_date = unlogged.loc[
            unlogged["plan_date"].dt.date
            == selected_date
        ]

        st.caption(
            f"{len(meals_on_date)} unlogged meal(s) "
            "are planned for this date."
        )

        if st.button(
            "Log all meals for this date",
            type="primary",
            width="stretch",
            key="log_all_planned_meals_for_day",
        ):
            try:
                logged_count, pantry_warnings = (
                    log_planned_meals_for_date(
                        selected_date
                    )
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The meals could not be logged: {error}"
                )

            else:
                st.success(
                    f"{logged_count} planned meal(s) logged."
                )
                st.rerun()

def render() -> None:
    st.title("Weekly Meal Planner")

    st.caption(
        "Plan recipes and automatically calculate weekly "
        "nutrition, cost, and shopping requirements."
    )

    default_start, default_end = get_current_week()

    week_start = st.date_input(
        "Week starting",
        value=default_start,
        format="MM/DD/YYYY",
        width="stretch",
    )

    week_end = week_start + timedelta(days=6)

    st.caption(
        f"Planning period: "
        f"{week_start.strftime('%B %d')}–"
        f"{week_end.strftime('%B %d, %Y')}"
    )

    add_tab, view_tab = st.tabs(
        [
            "Add Planned Meal",
            "View Week",
        ]
    )

    with add_tab:
        render_add_planned_meal(
            week_start=week_start,
            week_end=week_end,
        )

    meal_plan = get_meal_plan(
        start_date=week_start,
        end_date=week_end,
    )

    with view_tab:
        render_week_summary(meal_plan)
        render_plan_table(meal_plan)
        render_log_planned_meals(meal_plan)
        render_delete_section(meal_plan)
        render_clear_week(
            week_start=week_start,
            week_end=week_end,
            meal_plan=meal_plan,
        )