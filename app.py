import streamlit as st

from pages import analytics
from pages import dashboard
from pages import ingredients
from pages import meal_log
from pages import meal_planner
from pages import pantry
from pages import recipes
from pages import settings
from pages import shopping_list
from pages import shopping_trips


st.set_page_config(
    page_title="Nutrition Dashboard",
    page_icon="🍠",
    layout="wide",
    initial_sidebar_state="expanded",
)

dashboard_page = st.Page(
    dashboard.render,
    title="Dashboard",
    icon=":material/dashboard:",
    url_path="dashboard",
    default=True,
)

recipes_page = st.Page(
    recipes.render,
    title="Recipes",
    icon=":material/menu_book:",
    url_path="recipes",
)

ingredients_page = st.Page(
    ingredients.render,
    title="Ingredients",
    icon=":material/grocery:",
    url_path="ingredients",
)

meal_log_page = st.Page(
    meal_log.render,
    title="Meal Log",
    icon=":material/restaurant:",
    url_path="meal-log",
)

meal_planner_page = st.Page(
    meal_planner.render,
    title="Meal Planner",
    icon=":material/calendar_month:",
    url_path="meal-planner",
)

shopping_list_page = st.Page(
    shopping_list.render,
    title="Shopping List",
    icon=":material/shopping_cart:",
    url_path="shopping-list",
)

analytics_page = st.Page(
    analytics.render,
    title="Analytics",
    icon=":material/analytics:",
    url_path="analytics",
)

settings_page = st.Page(
    settings.render,
    title="Settings",
    icon=":material/settings:",
    url_path="settings",
)

pantry_page = st.Page(
    pantry.render,
    title="Pantry",
    icon=":material/inventory_2:",
    url_path="pantry",
)

shopping_trips_page = st.Page(
    shopping_trips.render,
    title="Shopping Trips",
    icon=":material/local_grocery_store:",
    url_path="shopping-trips",
)

navigation = st.navigation(
    {
        "Overview": [
            dashboard_page,
            analytics_page,
        ],
        "Planning": [
            meal_planner_page,
            shopping_list_page,
            shopping_trips_page,
            pantry_page,
        ],
        "Nutrition": [
            meal_log_page,
            recipes_page,
            ingredients_page,
        ],
        "Application": [
            settings_page,
        ],
    }
)

navigation.run()