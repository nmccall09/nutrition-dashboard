from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from services.meal_log_service import (
    get_daily_nutrition,
    get_meal_log,
)
from services.settings_service import get_setting


def create_complete_date_range(
    daily_data: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Include zero-value rows for days without meal logs.
    """
    complete_dates = pd.DataFrame(
        {
            "meal_date": pd.date_range(
                start=start_date,
                end=end_date,
                freq="D",
            )
        }
    )

    if daily_data.empty:
        complete_dates["calories"] = 0.0
        complete_dates["protein"] = 0.0
        complete_dates["carbs"] = 0.0
        complete_dates["fat"] = 0.0
        complete_dates["estimated_cost"] = 0.0
        complete_dates["meals_logged"] = 0

        return complete_dates

    result = complete_dates.merge(
        daily_data,
        how="left",
        on="meal_date",
    )

    numeric_columns = [
        "calories",
        "protein",
        "carbs",
        "fat",
        "estimated_cost",
        "meals_logged",
    ]

    result[numeric_columns] = (
        result[numeric_columns].fillna(0)
    )

    return result


def render_today_metrics(
    daily_data: pd.DataFrame,
    protein_goal: float,
    calorie_goal: float,
) -> None:
    today_timestamp = pd.Timestamp(date.today())

    today_rows = daily_data.loc[
        daily_data["meal_date"] == today_timestamp
    ]

    if today_rows.empty:
        calories = 0.0
        protein = 0.0
        cost = 0.0
        meals = 0
    else:
        today_row = today_rows.iloc[0]

        calories = float(today_row["calories"])
        protein = float(today_row["protein"])
        cost = float(today_row["estimated_cost"])
        meals = int(today_row["meals_logged"])

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Protein Today",
        f"{protein:.1f} g",
        delta=f"{protein - protein_goal:+.1f} g vs goal",
        border=True,
    )

    metric_columns[1].metric(
        "Calories Today",
        f"{calories:,.0f}",
        delta=f"{calorie_goal - calories:,.0f} remaining",
        border=True,
    )

    metric_columns[2].metric(
        "Meals Logged",
        f"{meals}",
        border=True,
    )

    metric_columns[3].metric(
        "Estimated Food Cost",
        f"${cost:.2f}",
        border=True,
    )

    protein_progress = min(
        protein / protein_goal,
        1.0,
    ) if protein_goal > 0 else 0

    calorie_progress = min(
        calories / calorie_goal,
        1.0,
    ) if calorie_goal > 0 else 0

    progress_columns = st.columns(2)

    with progress_columns[0]:
        st.write("**Protein Goal**")

        st.progress(
            protein_progress,
            text=(
                f"{protein:.1f} / "
                f"{protein_goal:.0f} g"
            ),
        )

    with progress_columns[1]:
        st.write("**Calorie Goal**")

        st.progress(
            calorie_progress,
            text=(
                f"{calories:.0f} / "
                f"{calorie_goal:.0f} calories"
            ),
        )


def render_trend_charts(
    daily_data: pd.DataFrame,
    protein_goal: float,
    calorie_goal: float,
) -> None:
    st.subheader("Last Seven Days")

    protein_figure = px.bar(
        daily_data,
        x="meal_date",
        y="protein",
        title="Daily Protein",
        labels={
            "meal_date": "Date",
            "protein": "Protein (g)",
        },
    )

    protein_figure.add_hline(
        y=protein_goal,
        line_dash="dash",
        annotation_text="Protein Goal",
    )

    protein_figure.update_layout(
        showlegend=False,
        xaxis_title=None,
    )

    calorie_figure = px.line(
        daily_data,
        x="meal_date",
        y="calories",
        markers=True,
        title="Daily Calories",
        labels={
            "meal_date": "Date",
            "calories": "Calories",
        },
    )

    calorie_figure.add_hline(
        y=calorie_goal,
        line_dash="dash",
        annotation_text="Calorie Goal",
    )

    calorie_figure.update_layout(
        showlegend=False,
        xaxis_title=None,
    )

    left, right = st.columns(2)

    with left:
        st.plotly_chart(
            protein_figure,
            width="stretch",
        )

    with right:
        st.plotly_chart(
            calorie_figure,
            width="stretch",
        )

def render_weekly_summary(
    daily_data: pd.DataFrame,
    weekly_grocery_budget: float,
) -> None:
    st.subheader("Weekly Summary")

    logged_days = daily_data.loc[
        daily_data["meals_logged"] > 0
    ]

    total_protein = float(
        daily_data["protein"].sum()
    )

    total_calories = float(
        daily_data["calories"].sum()
    )

    total_cost = float(
        daily_data["estimated_cost"].sum()
    )

    average_protein = (
        float(logged_days["protein"].mean())
        if not logged_days.empty
        else 0.0
    )

    remaining_budget = (
        weekly_grocery_budget - total_cost
    )

    summary_columns = st.columns(5)

    summary_columns[0].metric(
        "Total Protein",
        f"{total_protein:,.1f} g",
        border=True,
    )

    summary_columns[1].metric(
        "Avg Protein / Logged Day",
        f"{average_protein:,.1f} g",
        border=True,
    )

    summary_columns[2].metric(
        "Total Calories",
        f"{total_calories:,.0f}",
        border=True,
    )

    summary_columns[3].metric(
        "Estimated Weekly Cost",
        f"${total_cost:,.2f}",
        border=True,
    )

    summary_columns[4].metric(
        "Budget Remaining",
        f"${remaining_budget:,.2f}",
        delta=(
            "Under budget"
            if remaining_budget >= 0
            else "Over budget"
        ),
        delta_color=(
            "normal"
            if remaining_budget >= 0
            else "inverse"
        ),
        border=True,
    )

def render_recent_meals() -> None:
    st.subheader("Recent Meals")

    recent_meals = get_meal_log(
        start_date=date.today() - timedelta(days=6),
        end_date=date.today(),
    )

    if recent_meals.empty:
        st.info(
            "No meals have been logged yet."
        )
        return

    display = recent_meals[
        [
            "meal_date",
            "meal_type",
            "recipe_name",
            "servings",
            "calories",
            "protein",
        ]
    ].head(10)

    display = display.rename(
        columns={
            "meal_date": "Date",
            "meal_type": "Meal",
            "recipe_name": "Recipe",
            "servings": "Servings",
            "calories": "Calories",
            "protein": "Protein",
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
        },
    )


def render() -> None:
    st.title("Nutrition Dashboard")

    st.caption(
        "Track your daily protein, calories, meal frequency, "
        "and estimated food cost."
    )

    protein_goal = get_setting(
        "daily_protein_goal",
        180,
    )

    calorie_goal = get_setting(
        "daily_calorie_goal",
        2200,
    )

    weekly_grocery_budget = get_setting(
        "weekly_grocery_budget",
        100,
    )

    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    daily_data = get_daily_nutrition(
        start_date=start_date,
        end_date=end_date,
    )

    daily_data = create_complete_date_range(
        daily_data=daily_data,
        start_date=start_date,
        end_date=end_date,
    )

    render_today_metrics(
        daily_data=daily_data,
        protein_goal=protein_goal,
        calorie_goal=calorie_goal,
    )

    st.divider()

    render_trend_charts(
        daily_data=daily_data,
        protein_goal=protein_goal,
        calorie_goal=calorie_goal,
    )

    render_weekly_summary(
        daily_data=daily_data,
        weekly_grocery_budget=weekly_grocery_budget,
    )

    st.divider()

    render_recent_meals()