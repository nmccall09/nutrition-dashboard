import psycopg

import streamlit as st

from services.settings_service import (
    get_all_settings,
    update_nutrition_settings,
)


def render() -> None:
    st.title("Settings")

    st.caption(
        "Manage your daily nutrition targets and weekly "
        "grocery budget."
    )

    settings = get_all_settings()

    with st.form(
        "nutrition_settings_form",
    ):
        st.subheader("Nutrition Goals")

        left, middle, right = st.columns(3)

        with left:
            protein_goal = st.number_input(
                "Daily protein goal (g)",
                min_value=1.0,
                max_value=500.0,
                value=float(
                    settings["daily_protein_goal"]
                ),
                step=5.0,
            )

        with middle:
            calorie_goal = st.number_input(
                "Daily calorie goal",
                min_value=500.0,
                max_value=10000.0,
                value=float(
                    settings["daily_calorie_goal"]
                ),
                step=50.0,
            )

        with right:
            grocery_budget = st.number_input(
                "Weekly grocery budget",
                min_value=0.0,
                max_value=5000.0,
                value=float(
                    settings["weekly_grocery_budget"]
                ),
                step=5.0,
                format="%.2f",
            )

        submitted = st.form_submit_button(
            "Save settings",
            type="primary",
            width="stretch",
        )

    if submitted:
        try:
            update_nutrition_settings(
                daily_protein_goal=protein_goal,
                daily_calorie_goal=calorie_goal,
                weekly_grocery_budget=grocery_budget,
            )

        except psycopg.Error as error:
            st.error(
                f"Settings could not be saved: {error}"
            )

        else:
            st.success("Settings saved successfully.")
            st.rerun()

    st.divider()

    st.subheader("Current Goals")

    metric_columns = st.columns(3)

    metric_columns[0].metric(
        "Protein",
        f"{settings['daily_protein_goal']:,.0f} g/day",
        border=True,
    )

    metric_columns[1].metric(
        "Calories",
        f"{settings['daily_calorie_goal']:,.0f}/day",
        border=True,
    )

    metric_columns[2].metric(
        "Grocery Budget",
        f"${settings['weekly_grocery_budget']:,.2f}/week",
        border=True,
    )