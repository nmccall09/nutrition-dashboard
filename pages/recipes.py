import psycopg

import pandas as pd
import streamlit as st

from services.recipe_service import (
    add_recipe,
    delete_recipe,
    get_all_recipes,
    get_recipe_by_id,
    update_recipe,
)


MEAL_TYPES = [
    "Breakfast",
    "Lunch",
    "Dinner",
    "Snack",
]


def calculate_protein_efficiency(
    protein: float,
    calories: float,
) -> float:
    """
    Calculate grams of protein per 100 calories.
    """
    if calories <= 0:
        return 0.0

    return protein / calories * 100


def render_add_recipe_form() -> None:
    st.subheader("Add a Recipe")

    with st.form(
        key="add_recipe_form",
        clear_on_submit=True,
    ):
        recipe_name = st.text_input(
            "Recipe name",
            placeholder="Ground Beef Sweet Potato Bowl",
        )

        meal_type = st.selectbox(
            "Meal type",
            options=MEAL_TYPES,
        )

        servings = st.number_input(
            "Recipe servings",
            min_value=0.25,
            value=1.0,
            step=0.25,
            help=(
                "Use 1 if the nutrition information already represents "
                "one prepared meal."
            ),
        )

        st.markdown("#### Nutrition per serving")

        calories_column, protein_column = st.columns(2)

        with calories_column:
            calories = st.number_input(
                "Calories",
                min_value=0.0,
                value=0.0,
                step=10.0,
            )

        with protein_column:
            protein = st.number_input(
                "Protein (g)",
                min_value=0.0,
                value=0.0,
                step=1.0,
            )

        carbs_column, fat_column = st.columns(2)

        with carbs_column:
            carbs = st.number_input(
                "Carbohydrates (g)",
                min_value=0.0,
                value=0.0,
                step=1.0,
            )

        with fat_column:
            fat = st.number_input(
                "Fat (g)",
                min_value=0.0,
                value=0.0,
                step=1.0,
            )

        prep_column, cost_column = st.columns(2)

        with prep_column:
            prep_minutes = st.number_input(
                "Prep time (minutes)",
                min_value=0,
                value=0,
                step=5,
            )

        with cost_column:
            cost_per_serving = st.number_input(
                "Estimated cost per serving",
                min_value=0.0,
                value=0.0,
                step=0.25,
                format="%.2f",
            )

        instructions = st.text_area(
            "Instructions",
            placeholder=(
                "1. Roast the sweet potatoes.\n"
                "2. Brown the ground beef.\n"
                "3. Divide into meal-prep containers."
            ),
            height=150,
        )

        notes = st.text_area(
            "Notes",
            placeholder=(
                "Freezer friendly, add salsa after reheating, "
                "works well with spinach..."
            ),
            height=90,
        )

        submitted = st.form_submit_button(
            "Save recipe",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    validation_errors: list[str] = []

    if not recipe_name.strip():
        validation_errors.append("Enter a recipe name.")

    if calories <= 0:
        validation_errors.append(
            "Calories per serving must be greater than zero."
        )

    if protein <= 0:
        validation_errors.append(
            "Protein per serving must be greater than zero."
        )

    if validation_errors:
        for error in validation_errors:
            st.error(error)

        return

    try:
        recipe_id = add_recipe(
            recipe_name=recipe_name,
            meal_type=meal_type,
            servings=servings,
            calories_per_serving=calories,
            protein_per_serving=protein,
            carbs_per_serving=carbs,
            fat_per_serving=fat,
            prep_minutes=prep_minutes,
            estimated_cost_per_serving=cost_per_serving,
            instructions=instructions,
            notes=notes,
        )

    except psycopg.IntegrityError as error:
        st.error(
            "A recipe with that name already exists. "
            "Use a different name."
        )

    except psycopg.Error as error:
        st.error(f"The recipe could not be saved: {error}")

    else:
        st.success(
            f"Recipe saved successfully with ID {recipe_id}."
        )

def prepare_recipe_display(
    recipes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add calculated analytics fields and clean column labels.
    """
    display = recipes.copy()

    display["protein_efficiency"] = (
        display["protein_per_serving"]
        / display["calories_per_serving"]
        * 100
    )

    display["protein_per_dollar"] = display.apply(
        lambda row: (
            row["protein_per_serving"]
            / row["effective_cost_per_serving"]
            if row["effective_cost_per_serving"] > 0
            else 0
        ),
        axis=1,
    )

    display["cost_source"] = display[
        "ingredient_count"
    ].apply(
        lambda count: (
            "Ingredients"
            if count > 0
            else "Manual estimate"
        )
    )

    display = display[
        [
            "recipe_id",
            "recipe_name",
            "meal_type",
            "calories_per_serving",
            "protein_per_serving",
            "protein_efficiency",
            "effective_cost_per_serving",
            "protein_per_dollar",
            "cost_source",
            "prep_minutes",
        ]
    ]

    return display.rename(
        columns={
            "recipe_id": "ID",
            "recipe_name": "Recipe",
            "meal_type": "Meal",
            "calories_per_serving": "Calories",
            "protein_per_serving": "Protein (g)",
            "protein_efficiency": "Protein / 100 Cal",
            "effective_cost_per_serving": (
                "Cost / Serving"
            ),
            "protein_per_dollar": (
                "Protein / Dollar"
            ),
            "cost_source": "Cost Source",
            "prep_minutes": "Prep Minutes",
        }
    )

def render_edit_recipe_form() -> None:
    st.subheader("Edit a Recipe")

    recipes = get_all_recipes()

    if recipes.empty:
        st.info(
            "Add a recipe before using the edit feature."
        )
        return

    recipe_options = {
        (
            f"{row.recipe_name} "
            f"({row.meal_type}, ID {row.recipe_id})"
        ): int(row.recipe_id)
        for row in recipes.itertuples()
    }

    selected_label = st.selectbox(
        "Choose a recipe to edit",
        options=list(recipe_options.keys()),
        key="edit_recipe_selection",
        width="stretch",
    )

    selected_id = recipe_options[selected_label]
    recipe = get_recipe_by_id(selected_id)

    if recipe is None:
        st.error("The selected recipe could not be found.")
        return

    meal_type_index = MEAL_TYPES.index(
        recipe["meal_type"]
    )

    with st.form(
        key=f"edit_recipe_form_{selected_id}",
    ):
        recipe_name = st.text_input(
            "Recipe name",
            value=recipe["recipe_name"],
        )

        meal_type = st.selectbox(
            "Meal type",
            options=MEAL_TYPES,
            index=meal_type_index,
        )

        servings = st.number_input(
            "Recipe servings",
            min_value=0.25,
            value=float(recipe["servings"]),
            step=0.25,
        )

        st.markdown("#### Nutrition per serving")

        calories_column, protein_column = st.columns(2)

        with calories_column:
            calories = st.number_input(
                "Calories",
                min_value=0.0,
                value=float(
                    recipe["calories_per_serving"]
                ),
                step=10.0,
            )

        with protein_column:
            protein = st.number_input(
                "Protein (g)",
                min_value=0.0,
                value=float(
                    recipe["protein_per_serving"]
                ),
                step=1.0,
            )

        carbs_column, fat_column = st.columns(2)

        with carbs_column:
            carbs = st.number_input(
                "Carbohydrates (g)",
                min_value=0.0,
                value=float(
                    recipe["carbs_per_serving"]
                ),
                step=1.0,
            )

        with fat_column:
            fat = st.number_input(
                "Fat (g)",
                min_value=0.0,
                value=float(
                    recipe["fat_per_serving"]
                ),
                step=1.0,
            )

        prep_column, cost_column = st.columns(2)

        with prep_column:
            prep_minutes = st.number_input(
                "Prep time (minutes)",
                min_value=0,
                value=int(
                    recipe["prep_minutes"] or 0
                ),
                step=5,
            )

        with cost_column:
            cost_per_serving = st.number_input(
                "Estimated cost per serving",
                min_value=0.0,
                value=float(
                    recipe[
                        "estimated_cost_per_serving"
                    ]
                    or 0
                ),
                step=0.25,
                format="%.2f",
            )

        instructions = st.text_area(
            "Instructions",
            value=recipe["instructions"] or "",
            height=150,
        )

        notes = st.text_area(
            "Notes",
            value=recipe["notes"] or "",
            height=90,
        )

        submitted = st.form_submit_button(
            "Save changes",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    validation_errors: list[str] = []

    if not recipe_name.strip():
        validation_errors.append(
            "Enter a recipe name."
        )

    if calories <= 0:
        validation_errors.append(
            "Calories per serving must be greater "
            "than zero."
        )

    if protein <= 0:
        validation_errors.append(
            "Protein per serving must be greater "
            "than zero."
        )

    if validation_errors:
        for error in validation_errors:
            st.error(error)

        return

    try:
        update_recipe(
            recipe_id=selected_id,
            recipe_name=recipe_name,
            meal_type=meal_type,
            servings=servings,
            calories_per_serving=calories,
            protein_per_serving=protein,
            carbs_per_serving=carbs,
            fat_per_serving=fat,
            prep_minutes=prep_minutes,
            estimated_cost_per_serving=(
                cost_per_serving
            ),
            instructions=instructions,
            notes=notes,
        )

    except psycopg.IntegrityError as error:
        st.error(
            "Another recipe already uses that name."
        )

    except (psycopg.Error, ValueError) as error:
        st.error(
            f"The recipe could not be updated: {error}"
        )

    else:
        st.success("Recipe updated successfully.")
        st.rerun()

def render_recipe_table() -> None:
    st.subheader("Saved Recipes")

    recipes = get_all_recipes()

    if recipes.empty:
        st.info(
            "You haven't saved any recipes yet. "
            "Add your first recipe using the form above."
        )
        return

    filter_column, sort_column = st.columns(2)

    with filter_column:
        meal_filter = st.multiselect(
            "Filter by meal",
            options=MEAL_TYPES,
            default=MEAL_TYPES,
        )

    with sort_column:
        sort_option = st.selectbox(
            "Sort by",
            options=[
                "Recipe name",
                "Highest protein",
                "Lowest calories",
                "Best protein efficiency",
                "Lowest cost",
                "Best protein per dollar",
            ],
        )

    filtered_recipes = recipes[
        recipes["meal_type"].isin(meal_filter)
    ].copy()

    display = prepare_recipe_display(filtered_recipes)

    sort_rules = {
        "Recipe name": ("Recipe", True),
        "Highest protein": ("Protein (g)", False),
        "Lowest calories": ("Calories", True),
        "Best protein efficiency": (
            "Protein / 100 Cal",
            False,
        ),
        "Lowest cost": ("Cost / Serving", True),
        "Best protein per dollar": (
            "Protein / Dollar",
            False,
        ),
    }

    sort_column_name, ascending = sort_rules[sort_option]

    display = display.sort_values(
        by=sort_column_name,
        ascending=ascending,
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Calories": st.column_config.NumberColumn(
                format="%.0f",
            ),
            "Protein (g)": st.column_config.NumberColumn(
                format="%.1f g",
            ),
            "Protein / 100 Cal": (
                st.column_config.NumberColumn(
                    format="%.2f g",
                    help=(
                        "Grams of protein provided for every "
                        "100 calories."
                    ),
                )
            ),
            "Cost / Serving": st.column_config.NumberColumn(
                format="$%.2f",
            ),
            "Protein / Dollar": (
                st.column_config.NumberColumn(
                    format="%.2f g",
                    help=(
                        "Estimated grams of protein obtained "
                        "per dollar spent."
                    ),
                )
            ),
        },
    )

    render_delete_recipe_section(recipes)


def render_delete_recipe_section(
    recipes: pd.DataFrame,
) -> None:
    with st.expander("Delete a recipe"):
        recipe_options = {
            (
                f"{row.recipe_name} "
                f"({row.meal_type}, ID {row.recipe_id})"
            ): int(row.recipe_id)
            for row in recipes.itertuples()
        }

        selected_label = st.selectbox(
            "Choose a recipe",
            options=list(recipe_options.keys()),
            key="delete_recipe_selection",
        )

        confirmation = st.checkbox(
            "I understand this will permanently delete the recipe.",
            key="delete_recipe_confirmation",
        )

        if st.button(
            "Delete selected recipe",
            type="secondary",
            disabled=not confirmation,
        ):
            selected_id = recipe_options[selected_label]

            try:
                delete_recipe(selected_id)

            except psycopg.IntegrityError as error:
                st.error(
                    "This recipe is already referenced by another "
                    "record and cannot be deleted."
                )

            except psycopg.Error as error:
                st.error(
                    f"The recipe could not be deleted: {error}"
                )

            else:
                st.success("Recipe deleted.")
                st.rerun()


def render() -> None:
    st.title("Recipes")

    st.caption(
        "Build a recipe database and compare meals by nutrition, "
        "cost, and protein efficiency."
    )

    add_tab, edit_tab, browse_tab = st.tabs(
    [
        "Add Recipe",
        "Edit Recipe",
        "Browse Recipes",
    ]
    )

    with add_tab:
        render_add_recipe_form()

    with edit_tab:
        render_edit_recipe_form()

    with browse_tab:
        render_recipe_table()