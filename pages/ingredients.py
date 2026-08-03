import pandas as pd
import psycopg

import streamlit as st

from services.recipe_service import (
    get_all_recipes,
    get_recipe_by_id,
)

from services.ingredient_service import (
    add_ingredient,
    add_ingredient_to_recipe,
    get_all_ingredients,
    get_recipe_ingredient_by_id,
    get_recipe_ingredients,
    remove_ingredient_from_recipe,
    update_recipe_ingredient,
)
from services.ingredient_service import (
    clear_ingredient_package,
    get_all_ingredients,
    update_ingredient_package,
)
from services.ingredient_service import (
    delete_ingredient,
    get_ingredient_usage,
    update_ingredient,
)

from services.ingredient_service import (
    archive_ingredient,
    restore_ingredient,
)


CATEGORIES = [
    "Protein",
    "Produce",
    "Dairy",
    "Pantry",
    "Frozen",
    "Condiment",
    "Seasoning",
    "Other",
]

STORES = [
    "Aldi",
    "Costco",
    "Other",
]

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

def render_edit_ingredient() -> None:
    st.subheader("Edit or Delete Ingredient")

    ingredients = get_all_ingredients(
        include_archived=True,
    )

    if ingredients.empty:
        st.info("No ingredients are available.")
        return

    options = {
        (
            f"{row.ingredient_name}"
            if bool(row.is_active)
            else f"{row.ingredient_name} (Archived)"
        ): int(row.ingredient_id)
        for row in ingredients.itertuples()
    }

    selected_name = st.selectbox(
        "Ingredient",
        options=list(options.keys()),
        key="edit_ingredient_selection",
    )

    ingredient_id = options[selected_name]

    ingredient = ingredients.loc[
        ingredients["ingredient_id"] == ingredient_id
    ].iloc[0]

    is_active = bool(
        ingredient["is_active"]
    )

    store_index = (
        STORES.index(ingredient["preferred_store"])
        if ingredient["preferred_store"] in STORES
        else 0
    )

    unit_options = [
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

    current_unit = str(ingredient["default_unit"])

    if current_unit not in unit_options:
        unit_options.append(current_unit)

    unit_index = unit_options.index(current_unit)

    with st.form(
        key=f"edit_ingredient_form_{ingredient_id}",
    ):
        ingredient_name = st.text_input(
            "Ingredient name",
            value=str(ingredient["ingredient_name"]),
        )

        category = st.text_input(
            "Category",
            value=str(ingredient["category"]),
        )

        preferred_store = st.selectbox(
            "Preferred store",
            options=STORES,
            index=store_index,
        )

        default_unit = st.selectbox(
            "Default unit",
            options=unit_options,
            index=unit_index,
        )

        estimated_unit_cost = st.number_input(
            "Estimated cost per unit",
            min_value=0.0,
            value=float(
                ingredient["estimated_unit_cost"] or 0
            ),
            step=0.001,
            format="%.4f",
        )

        submitted = st.form_submit_button(
            "Save ingredient changes",
            type="primary",
            width="stretch",
        )

    if submitted:
        try:
            update_ingredient(
                ingredient_id=ingredient_id,
                ingredient_name=ingredient_name,
                category=category,
                preferred_store=preferred_store,
                default_unit=default_unit,
                estimated_unit_cost=estimated_unit_cost,
            )

        except (
            psycopg.Error,
            ValueError,
        ) as error:
            st.error(
                f"The ingredient could not be updated: "
                f"{error}"
            )

        else:
            st.success("Ingredient updated.")
            st.rerun()

    st.divider()

    usage = get_ingredient_usage(
        ingredient_id
    )

    status_label = (
        "Active"
        if is_active
        else "Archived"
    )

    st.metric(
        "Ingredient Status",
        status_label,
        border=True,
    )

    st.caption(
        f"Used in {usage['recipe_count']:,} active recipe "
        f"assignment(s), {usage['pantry_count']:,} pantry "
        f"record(s), and {usage['shopping_trip_count']:,} "
        "historical shopping-trip item(s)."
    )

    if is_active:
        st.warning(
            "Archiving removes this ingredient from active "
            "recipes and pantry inventory. Historical shopping "
            "trips will remain unchanged."
        )

        confirmed = st.checkbox(
            "Confirm ingredient archive",
            key=(
                f"confirm_archive_ingredient_"
                f"{ingredient_id}"
            ),
        )

        if st.button(
            "Archive ingredient",
            disabled=not confirmed,
            key=f"archive_ingredient_{ingredient_id}",
        ):
            try:
                archive_ingredient(
                    ingredient_id
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The ingredient could not be archived: "
                    f"{error}"
                )

            else:
                st.success(
                    "Ingredient archived. Historical shopping "
                    "trips were preserved."
                )
                st.rerun()

    else:
        st.info(
            "This ingredient is archived and will not appear "
            "in new recipes, pantry entries, or shopping lists."
        )

        if st.button(
            "Restore ingredient",
            type="primary",
            width="stretch",
            key=f"restore_ingredient_{ingredient_id}",
        ):
            try:
                restore_ingredient(
                    ingredient_id
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"The ingredient could not be restored: "
                    f"{error}"
                )

            else:
                st.success("Ingredient restored.")
                st.rerun()


def render_add_ingredient_form() -> None:
    st.subheader("Add Ingredient")

    with st.form(
        "add_ingredient_form",
        clear_on_submit=True,
    ):
        ingredient_name = st.text_input(
            "Ingredient name",
            placeholder="93/7 ground beef",
        )

        left, right = st.columns(2)

        with left:
            category = st.selectbox(
                "Category",
                CATEGORIES,
            )

            preferred_store = st.selectbox(
                "Preferred store",
                STORES,
            )

        with right:
            default_unit = st.selectbox(
                "Default unit",
                UNITS,
            )

            estimated_unit_cost = st.number_input(
                "Estimated cost per unit",
                min_value=0.0,
                value=0.0,
                step=0.001,
                format="%.4f",
                help=(
                    "Enter the cost for one default unit. "
                    "For example, $0.0030 per gram."
                ),
            )

        submitted = st.form_submit_button(
            "Save ingredient",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not ingredient_name.strip():
        st.error("Enter an ingredient name.")
        return

    try:
        ingredient_id = add_ingredient(
            ingredient_name=ingredient_name,
            category=category,
            preferred_store=preferred_store,
            default_unit=default_unit,
            estimated_unit_cost=estimated_unit_cost,
        )

    except psycopg.IntegrityError as error:
        st.error(
            "An ingredient with that name already exists."
        )

    except psycopg.Error as error:
        st.error(
            f"The ingredient could not be saved: {error}"
        )

    else:
        st.success(
            f"Ingredient saved with ID {ingredient_id}."
        )

def render_ingredient_catalog() -> None:
    st.subheader("Ingredient Catalog")

    ingredients = get_all_ingredients()

    if ingredients.empty:
        st.info("No ingredients have been added yet.")
        return

    store_filter = st.multiselect(
        "Filter by store",
        options=STORES,
        default=STORES,
    )

    filtered = ingredients[
        ingredients["preferred_store"].isin(
            store_filter
        )
    ].copy()

    filtered = filtered[
        [
            "ingredient_id",
            "ingredient_name",
            "category",
            "preferred_store",
            "default_unit",
            "estimated_unit_cost",
            "package_quantity",
            "package_unit",
            "package_price",
            "package_description",
        ]
    ]

    filtered = filtered.rename(
        columns={
            "ingredient_id": "ID",
            "ingredient_name": "Ingredient",
            "category": "Category",
            "preferred_store": "Store",
            "default_unit": "Default Unit",
            "estimated_unit_cost": "Unit Cost",
            "package_quantity": "Package Quantity",
            "package_unit": "Package Unit",
            "package_price": "Package Price",
            "package_description": "Package Description",
        }
    )

    st.dataframe(
        filtered,
        hide_index=True,
        width="stretch",
        column_config={
            "Unit Cost": st.column_config.NumberColumn(
                format="$%.4f",
            ),
            "Package Quantity": (
                st.column_config.NumberColumn(
                    format="%,.3f",
                )
            ),
            "Package Price": (
                st.column_config.NumberColumn(
                    format="$%,.2f",
                )
            ),
        },
    )

def render_recipe_cost_summary(
    recipe: dict,
    assigned_ingredients,
) -> None:
    """
    Show ingredient cost totals and compare them with the
    manually entered recipe cost.
    """
    total_ingredient_cost = float(
        assigned_ingredients["estimated_cost"].sum()
    )

    servings = float(recipe["servings"])

    calculated_cost_per_serving = (
        total_ingredient_cost / servings
        if servings > 0
        else 0.0
    )

    manual_cost_per_serving = float(
        recipe["estimated_cost_per_serving"] or 0
    )

    cost_difference = (
        calculated_cost_per_serving
        - manual_cost_per_serving
    )

    total_column, calculated_column, manual_column = (
        st.columns(3)
    )

    with total_column:
        st.metric(
            label="Total Ingredient Cost",
            value=f"${total_ingredient_cost:.2f}",
            border=True,
        )

    with calculated_column:
        st.metric(
            label="Calculated Cost / Serving",
            value=f"${calculated_cost_per_serving:.2f}",
            border=True,
        )

    with manual_column:
        st.metric(
            label="Recipe Cost / Serving",
            value=f"${manual_cost_per_serving:.2f}",
            delta=f"${cost_difference:+.2f}",
            help=(
                "The delta compares calculated ingredient cost "
                "with the cost saved on the recipe."
            ),
            border=True,
        )

    if abs(cost_difference) < 0.01:
        st.success(
            "The calculated ingredient cost matches the "
            "recipe cost."
        )
    elif cost_difference > 0:
        st.warning(
            "The ingredient calculation is "
            f"${abs(cost_difference):.2f} higher per serving "
            "than the recipe's saved cost."
        )
    else:
        st.info(
            "The ingredient calculation is "
            f"${abs(cost_difference):.2f} lower per serving "
            "than the recipe's saved cost."
        )

def render_edit_recipe_ingredient(
    assigned_ingredients,
) -> None:
    """
    Edit quantity, unit, and cost for an ingredient already
    assigned to a recipe.
    """
    if assigned_ingredients.empty:
        return

    st.markdown("#### Edit Assigned Ingredient")

    assignment_options = {
        (
            f"{row.ingredient_name} — "
            f"{row.quantity:g} {row.unit}"
        ): int(row.recipe_ingredient_id)
        for row in assigned_ingredients.itertuples()
    }

    selected_label = st.selectbox(
        "Choose an ingredient to edit",
        options=list(assignment_options.keys()),
        key="edit_assignment_selection",
    )

    assignment_id = assignment_options[selected_label]

    assignment = get_recipe_ingredient_by_id(
        assignment_id
    )

    if assignment is None:
        st.error(
            "The selected ingredient assignment could not "
            "be found."
        )
        return

    current_unit = assignment["unit"]

    if current_unit in UNITS:
        unit_index = UNITS.index(current_unit)
    else:
        unit_index = 0

    with st.form(
        key=f"edit_assignment_form_{assignment_id}",
    ):
        st.write(
            f"Editing **{assignment['ingredient_name']}**"
        )

        quantity_column, unit_column, cost_column = (
            st.columns(3)
        )

        with quantity_column:
            quantity = st.number_input(
                "Quantity",
                min_value=0.01,
                value=float(assignment["quantity"]),
                step=0.25,
            )

        with unit_column:
            unit = st.selectbox(
                "Unit",
                options=UNITS,
                index=unit_index,
            )

        with cost_column:
            estimated_cost = st.number_input(
                "Estimated cost used",
                min_value=0.0,
                value=float(
                    assignment["estimated_cost"]
                ),
                step=0.05,
                format="%.2f",
            )

        submitted = st.form_submit_button(
            "Save ingredient changes",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    try:
        update_recipe_ingredient(
            recipe_ingredient_id=assignment_id,
            quantity=quantity,
            unit=unit,
            estimated_cost=estimated_cost,
        )

    except (psycopg.Error, ValueError) as error:
        st.error(
            "The ingredient assignment could not be "
            f"updated: {error}"
        )

    else:
        st.success("Ingredient assignment updated.")
        st.rerun()

def render_recipe_assignment() -> None:
    st.subheader("Assign Ingredients to a Recipe")

    recipes = get_all_recipes()
    ingredients = get_all_ingredients()

    if recipes.empty:
        st.info("Add a recipe first.")
        return

    if ingredients.empty:
        st.info("Add an ingredient first.")
        return

    recipe_options = {
        (
            f"{row.recipe_name} "
            f"({row.meal_type}, ID {row.recipe_id})"
        ): int(row.recipe_id)
        for row in recipes.itertuples()
    }

    ingredient_options = {
        row.ingredient_name: int(row.ingredient_id)
        for row in ingredients.itertuples()
    }

    selected_recipe_label = st.selectbox(
        "Recipe",
        options=list(recipe_options.keys()),
        key="ingredient_recipe_selection",
    )

    recipe_id = recipe_options[selected_recipe_label]
    recipe = get_recipe_by_id(recipe_id)

    if recipe is None:
        st.error("The selected recipe could not be found.")
        return

    selected_ingredient_name = st.selectbox(
        "Ingredient",
        options=list(ingredient_options.keys()),
        key="ingredient_assignment_selection",
    )

    ingredient_id = ingredient_options[
        selected_ingredient_name
    ]

    selected_ingredient_rows = ingredients.loc[
        ingredients["ingredient_id"] == ingredient_id
    ]

    if selected_ingredient_rows.empty:
        st.error(
            "The selected ingredient could not be found."
        )
        return

    selected_ingredient = selected_ingredient_rows.iloc[0]

    default_unit = str(
        selected_ingredient["default_unit"]
    )

    estimated_unit_cost = float(
        selected_ingredient["estimated_unit_cost"] or 0
    )

    default_unit_index = (
        UNITS.index(default_unit)
        if default_unit in UNITS
        else 0
    )

    left, middle = st.columns(2)

    with left:
        quantity = st.number_input(
            "Quantity",
            min_value=0.01,
            value=1.0,
            step=0.25,
            key=(
                f"assignment_quantity_"
                f"{recipe_id}_{ingredient_id}"
            ),
        )

    with middle:
        unit = st.selectbox(
            "Unit",
            options=UNITS,
            index=default_unit_index,
            key=(
                f"assignment_unit_"
                f"{recipe_id}_{ingredient_id}"
            ),
            help=(
                "Defaults to the unit saved in the "
                "ingredient catalog."
            ),
        )

    units_match = unit == default_unit

    if units_match:
        calculated_cost = (
            quantity * estimated_unit_cost
        )
    else:
        calculated_cost = 0.0

    manual_override = st.checkbox(
        "Override calculated cost",
        value=not units_match,
        key=(
            f"assignment_cost_override_"
            f"{recipe_id}_{ingredient_id}"
        ),
        help=(
            "Use this when the selected unit differs from "
            "the ingredient's default unit or when the "
            "actual price is different."
        ),
    )

    if manual_override:
        estimated_cost = st.number_input(
            "Estimated cost used",
            min_value=0.0,
            value=float(calculated_cost),
            step=0.05,
            format="%.2f",
            key=(
                f"assignment_manual_cost_"
                f"{recipe_id}_{ingredient_id}"
            ),
        )
    else:
        estimated_cost = calculated_cost

        st.metric(
            "Estimated Cost Used",
            f"${estimated_cost:.2f}",
            help=(
                f"{quantity:g} {unit} × "
                f"${estimated_unit_cost:.4f} per {default_unit}"
            ),
            border=True,
        )

    if not units_match:
        st.warning(
            "The selected unit differs from the ingredient's "
            f"default unit ({default_unit}). Enter the cost "
            "manually unless you add unit-conversion logic."
        )

    if st.button(
        "Add to recipe",
        type="primary",
        width="stretch",
        key=(
            f"add_assignment_"
            f"{recipe_id}_{ingredient_id}"
        ),
    ):
        try:
            add_ingredient_to_recipe(
                recipe_id=recipe_id,
                ingredient_id=ingredient_id,
                quantity=quantity,
                unit=unit,
                estimated_cost=estimated_cost,
            )

        except psycopg.IntegrityError as error:
            st.error(
                "That ingredient is already assigned to "
                "this recipe."
            )

        except psycopg.Error as error:
            st.error(
                "The ingredient could not be assigned: "
                f"{error}"
            )

        else:
            st.success("Ingredient added to recipe.")
            st.rerun()

    assigned = get_recipe_ingredients(recipe_id)

    if assigned.empty:
        st.info(
            "This recipe does not have any ingredients yet."
        )
        return

    st.divider()

    render_recipe_cost_summary(
        recipe=recipe,
        assigned_ingredients=assigned,
    )

    st.markdown("#### Current Recipe Ingredients")

    display = assigned.rename(
        columns={
            "recipe_ingredient_id": "Assignment ID",
            "ingredient_name": "Ingredient",
            "category": "Category",
            "preferred_store": "Store",
            "quantity": "Quantity",
            "unit": "Unit",
            "estimated_cost": "Estimated Cost",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Assignment ID": None,
            "Estimated Cost": (
                st.column_config.NumberColumn(
                    format="$%.2f",
                )
            ),
        },
    )

    st.divider()

    render_edit_recipe_ingredient(assigned)

    with st.expander("Remove an ingredient"):
        removal_options = {
            (
                f"{row.ingredient_name} "
                f"({row.quantity:g} {row.unit})"
            ): int(row.recipe_ingredient_id)
            for row in assigned.itertuples()
        }

        selected_removal = st.selectbox(
            "Ingredient to remove",
            options=list(removal_options.keys()),
            key="remove_assignment_selection",
        )

        confirmed = st.checkbox(
            "Confirm removal",
            key="remove_assignment_confirmation",
        )

        if st.button(
            "Remove ingredient",
            disabled=not confirmed,
        ):
            try:
                remove_ingredient_from_recipe(
                    removal_options[selected_removal]
                )

            except psycopg.Error as error:
                st.error(
                    "The ingredient could not be removed: "
                    f"{error}"
                )

            else:
                st.success("Ingredient removed.")
                st.rerun()

def render() -> None:
    st.title("Ingredients")

    st.caption(
        "Create a reusable ingredient catalog and assign "
        "ingredients to recipes."
    )

    add_tab, catalog_tab, assignment_tab, package_tab, edit_tab = st.tabs(
        [
            "Add Ingredient",
            "Ingredient Catalog",
            "Recipe Assignments",
            "Package Details",
            "Edit or Delete",
        ]
    )

    with add_tab:
        render_add_ingredient_form()

    with catalog_tab:
        render_ingredient_catalog()

    with assignment_tab:
        render_recipe_assignment()

    with package_tab:
        render_package_settings()

    with edit_tab:
        render_edit_ingredient()

def render_package_settings() -> None:
    st.subheader("Package Purchasing Details")

    ingredients = get_all_ingredients()

    if ingredients.empty:
        st.info(
            "Add an ingredient before entering package details."
        )
        return

    ingredient_options = {
        row.ingredient_name: int(row.ingredient_id)
        for row in ingredients.itertuples()
    }

    selected_name = st.selectbox(
        "Ingredient",
        options=list(ingredient_options.keys()),
        key="package_ingredient_selection",
    )

    ingredient_id = ingredient_options[selected_name]

    ingredient = ingredients.loc[
        ingredients["ingredient_id"] == ingredient_id
    ].iloc[0]

    existing_package_quantity = ingredient[
        "package_quantity"
    ]

    existing_package_unit = ingredient[
        "package_unit"
    ]

    existing_package_price = ingredient[
        "package_price"
    ]

    existing_description = (
        ingredient["package_description"]
        if pd.notna(
            ingredient["package_description"]
        )
        else ""
    )

    has_existing_package = (
        pd.notna(existing_package_quantity)
        and pd.notna(existing_package_unit)
        and pd.notna(existing_package_price)
    )

    track_package = st.checkbox(
        "Track a standard purchase package",
        value=has_existing_package,
        key=f"track_package_{ingredient_id}",
    )

    if not track_package:
        if has_existing_package:
            st.caption(
                "Saving with package tracking disabled will "
                "remove the existing package details."
            )

        if st.button(
            "Remove package details",
            type="secondary",
            width="stretch",
            disabled=not has_existing_package,
            key=f"clear_package_{ingredient_id}",
        ):
            try:
                clear_ingredient_package(
                    ingredient_id
                )

            except (
                psycopg.Error,
                ValueError,
            ) as error:
                st.error(
                    f"Package details could not be removed: "
                    f"{error}"
                )

            else:
                st.success("Package details removed.")
                st.rerun()

        return

    unit_options = [
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

    default_package_unit = (
        str(existing_package_unit)
        if has_existing_package
        else str(ingredient["default_unit"])
    )

    if default_package_unit not in unit_options:
        unit_options.append(default_package_unit)

    package_unit_index = unit_options.index(
        default_package_unit
    )

    with st.form(
        key=f"package_form_{ingredient_id}",
    ):
        left, middle, right = st.columns(3)

        with left:
            package_quantity = st.number_input(
                "Package quantity",
                min_value=0.001,
                value=(
                    float(existing_package_quantity)
                    if has_existing_package
                    else 1.0
                ),
                step=0.25,
                format="%.3f",
                help=(
                    "Total amount contained in one purchased "
                    "package."
                ),
            )

        with middle:
            package_unit = st.selectbox(
                "Package unit",
                options=unit_options,
                index=package_unit_index,
            )

        with right:
            package_price = st.number_input(
                "Package price",
                min_value=0.0,
                value=(
                    float(existing_package_price)
                    if has_existing_package
                    else 0.0
                ),
                step=0.25,
                format="%.2f",
            )

        package_description = st.text_input(
            "Package description",
            value=existing_description,
            placeholder=(
                "Example: Costco 3 lb ground-beef package"
            ),
        )

        submitted = st.form_submit_button(
            "Save package details",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    try:
        update_ingredient_package(
            ingredient_id=ingredient_id,
            package_quantity=package_quantity,
            package_unit=package_unit,
            package_price=package_price,
            package_description=package_description,
        )

    except (
        psycopg.Error,
        ValueError,
    ) as error:
        st.error(
            f"Package details could not be saved: {error}"
        )

    else:
        st.success("Package details saved.")
        st.rerun()