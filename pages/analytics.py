from datetime import date, timedelta

import plotly.express as px
import streamlit as st

from services.analytics_service import (
    get_period_summary,
    get_recipe_analytics,
)


MEAL_TYPES = [
    "Breakfast",
    "Lunch",
    "Dinner",
    "Snack",
]


def render_summary_metrics(
    start_date: date,
    end_date: date,
) -> None:
    summary = get_period_summary(
        start_date=start_date,
        end_date=end_date,
    )

    average_protein = (
        summary["protein"]
        / summary["days_logged"]
        if summary["days_logged"] > 0
        else 0
    )

    metric_columns = st.columns(5)

    metric_columns[0].metric(
        "Meals Logged",
        f"{summary['meals_logged']:,}",
        border=True,
    )

    metric_columns[1].metric(
        "Days Logged",
        f"{summary['days_logged']:,}",
        border=True,
    )

    metric_columns[2].metric(
        "Total Protein",
        f"{summary['protein']:,.1f} g",
        border=True,
    )

    metric_columns[3].metric(
        "Average Protein / Day",
        f"{average_protein:,.1f} g",
        border=True,
    )

    metric_columns[4].metric(
        "Estimated Cost",
        f"${summary['estimated_cost']:,.2f}",
        border=True,
    )


def render_recipe_rankings(
    analytics,
) -> None:
    st.subheader("Recipe Rankings")

    if analytics.empty:
        st.info("No recipes are available.")
        return

    left, right = st.columns(2)

    with left:
        meal_filter = st.multiselect(
            "Meal type",
            options=MEAL_TYPES,
            default=MEAL_TYPES,
        )

    with right:
        ranking_metric = st.selectbox(
            "Rank recipes by",
            options=[
                "Protein per 100 Calories",
                "Protein per Dollar",
                "Protein per Serving",
                "Lowest Calories",
                "Lowest Cost",
                "Most Frequently Logged",
            ],
        )

    filtered = analytics.loc[
        analytics["meal_type"].isin(meal_filter)
    ].copy()

    ranking_rules = {
        "Protein per 100 Calories": (
            "protein_per_100_calories",
            False,
        ),
        "Protein per Dollar": (
            "protein_per_dollar",
            False,
        ),
        "Protein per Serving": (
            "protein_per_serving",
            False,
        ),
        "Lowest Calories": (
            "calories_per_serving",
            True,
        ),
        "Lowest Cost": (
            "effective_cost_per_serving",
            True,
        ),
        "Most Frequently Logged": (
            "times_logged",
            False,
        ),
    }

    sort_column, ascending = ranking_rules[
        ranking_metric
    ]

    ranked = filtered.sort_values(
        by=sort_column,
        ascending=ascending,
    )

    display = ranked[
        [
            "recipe_name",
            "meal_type",
            "calories_per_serving",
            "protein_per_serving",
            "protein_per_100_calories",
            "effective_cost_per_serving",
            "protein_per_dollar",
            "times_logged",
            "servings_logged",
            "cost_source",
        ]
    ].copy()

    display = display.rename(
        columns={
            "recipe_name": "Recipe",
            "meal_type": "Meal",
            "calories_per_serving": "Calories",
            "protein_per_serving": "Protein",
            "protein_per_100_calories": (
                "Protein / 100 Cal"
            ),
            "effective_cost_per_serving": (
                "Cost / Serving"
            ),
            "protein_per_dollar": (
                "Protein / Dollar"
            ),
            "times_logged": "Times Logged",
            "servings_logged": "Servings Logged",
            "cost_source": "Cost Source",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Calories": st.column_config.NumberColumn(
                format="%,.0f",
            ),
            "Protein": st.column_config.NumberColumn(
                format="%,.1f g",
            ),
            "Protein / 100 Cal": (
                st.column_config.NumberColumn(
                    format="%.2f g",
                )
            ),
            "Cost / Serving": (
                st.column_config.NumberColumn(
                    format="$%,.2f",
                )
            ),
            "Protein / Dollar": (
                st.column_config.NumberColumn(
                    format="%.2f g",
                )
            ),
            "Times Logged": (
                st.column_config.NumberColumn(
                    format="%,d",
                )
            ),
            "Servings Logged": (
                st.column_config.NumberColumn(
                    format="%,.2f",
                )
            ),
        },
    )


def render_efficiency_chart(
    analytics,
) -> None:
    st.subheader("Protein Efficiency")

    if analytics.empty:
        return

    figure = px.scatter(
        analytics,
        x="calories_per_serving",
        y="protein_per_serving",
        size="effective_cost_per_serving",
        color="meal_type",
        hover_name="recipe_name",
        hover_data={
            "calories_per_serving": ":,.0f",
            "protein_per_serving": ":,.1f",
            "effective_cost_per_serving": "$:,.2f",
            "protein_per_100_calories": ":.2f",
            "protein_per_dollar": ":.2f",
        },
        labels={
            "calories_per_serving": (
                "Calories per Serving"
            ),
            "protein_per_serving": (
                "Protein per Serving (g)"
            ),
            "meal_type": "Meal",
        },
        title=(
            "Protein vs. Calories "
            "(bubble size represents cost)"
        ),
    )

    figure.update_layout(
        xaxis_title="Calories per Serving",
        yaxis_title="Protein per Serving (g)",
    )

    st.plotly_chart(
        figure,
        width="stretch",
    )


def render_cost_chart(
    analytics,
) -> None:
    st.subheader("Protein per Dollar")

    if analytics.empty:
        return

    chart_data = analytics.sort_values(
        by="protein_per_dollar",
        ascending=True,
    )

    figure = px.bar(
        chart_data,
        x="protein_per_dollar",
        y="recipe_name",
        orientation="h",
        color="meal_type",
        labels={
            "protein_per_dollar": (
                "Protein per Dollar (g)"
            ),
            "recipe_name": "Recipe",
            "meal_type": "Meal",
        },
        title="Estimated Protein Obtained per Dollar",
    )

    figure.update_layout(
        yaxis_title=None,
    )

    st.plotly_chart(
        figure,
        width="stretch",
    )


def render_usage_chart(
    analytics,
) -> None:
    st.subheader("Most Frequently Logged Recipes")

    if analytics.empty:
        return

    usage = analytics.loc[
        analytics["times_logged"] > 0
    ].copy()

    if usage.empty:
        st.info(
            "Log meals to populate recipe usage analytics."
        )
        return

    usage = usage.sort_values(
        by="times_logged",
        ascending=True,
    )

    figure = px.bar(
        usage,
        x="times_logged",
        y="recipe_name",
        orientation="h",
        color="meal_type",
        labels={
            "times_logged": "Times Logged",
            "recipe_name": "Recipe",
            "meal_type": "Meal",
        },
    )

    figure.update_layout(
        yaxis_title=None,
    )

    st.plotly_chart(
        figure,
        width="stretch",
    )


def render() -> None:
    st.title("Recipe Analytics")

    st.caption(
        "Compare recipes by nutrition, affordability, "
        "efficiency, and actual usage."
    )

    default_end = date.today()
    default_start = default_end - timedelta(days=29)

    left, right = st.columns(2)

    with left:
        start_date = st.date_input(
            "Summary start date",
            value=default_start,
            key="analytics_start_date",
        )

    with right:
        end_date = st.date_input(
            "Summary end date",
            value=default_end,
            key="analytics_end_date",
        )

    if start_date > end_date:
        st.error(
            "Start date cannot be after end date."
        )
        return

    render_summary_metrics(
        start_date=start_date,
        end_date=end_date,
    )

    st.divider()

    analytics = get_recipe_analytics()

    render_recipe_rankings(analytics)

    st.divider()

    render_efficiency_chart(analytics)

    left_chart, right_chart = st.columns(2)

    with left_chart:
        render_cost_chart(analytics)

    with right_chart:
        render_usage_chart(analytics)