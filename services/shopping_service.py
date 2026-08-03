from datetime import date
import math

import pandas as pd

from database.connection import query_dataframe
from services.unit_conversion_service import (
    can_convert_units,
    convert_quantity,
)

def get_generated_shopping_list(
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Generate shopping requirements, applying pantry and
    package conversions when units are compatible.
    """
    query = """
        WITH required_ingredients AS (
            SELECT
                i.ingredient_id,
                i.ingredient_name,
                i.category,
                i.preferred_store,

                i.package_quantity,
                i.package_unit,
                i.package_price,
                i.package_description,

                ri.unit,

                SUM(
                    ri.quantity
                    * mp.servings
                    / r.servings
                ) AS required_quantity,

                SUM(
                    ri.estimated_cost
                    * mp.servings
                    / r.servings
                ) AS full_required_cost

            FROM meal_plan AS mp

            JOIN recipes AS r
                ON mp.recipe_id = r.recipe_id

            JOIN recipe_ingredients AS ri
                ON mp.recipe_id = ri.recipe_id

            JOIN ingredients AS i
                ON ri.ingredient_id = i.ingredient_id

            WHERE mp.plan_date BETWEEN %s AND %s

            GROUP BY
                i.ingredient_id,
                i.ingredient_name,
                i.category,
                i.preferred_store,
                i.package_quantity,
                i.package_unit,
                i.package_price,
                i.package_description,
                ri.unit
        )

        SELECT
            req.*,

            p.pantry_id,
            p.quantity_on_hand
                AS raw_pantry_quantity,
            p.unit
                AS pantry_unit

        FROM required_ingredients AS req

        LEFT JOIN pantry_inventory AS p
            ON req.ingredient_id = p.ingredient_id

        ORDER BY
            CASE req.preferred_store
                WHEN 'Costco' THEN 1
                WHEN 'Aldi' THEN 2
                ELSE 3
            END,
            req.category,
            req.ingredient_name
    """

    result = query_dataframe(
        query,
        (
            start_date,
            end_date,
        ),
    )

    if result.empty:
        return result

    def calculate_pantry_quantity(row) -> float:
        if pd.isna(row["raw_pantry_quantity"]):
            return 0.0

        if pd.isna(row["pantry_unit"]):
            return 0.0

        if not can_convert_units(
            row["pantry_unit"],
            row["unit"],
        ):
            return 0.0

        return convert_quantity(
            quantity=float(
                row["raw_pantry_quantity"]
            ),
            from_unit=str(row["pantry_unit"]),
            to_unit=str(row["unit"]),
        )


    result["pantry_quantity"] = result.apply(
        calculate_pantry_quantity,
        axis=1,
    )

    result["purchase_quantity"] = (
        result["required_quantity"]
        - result["pantry_quantity"]
    ).clip(lower=0)

    result["estimated_cost"] = result.apply(
        lambda row: (
            (
                float(row["purchase_quantity"])
                / float(row["required_quantity"])
            )
            * float(row["full_required_cost"])
            if float(row["required_quantity"]) > 0
            else 0.0
        ),
        axis=1,
    )

    def calculate_pantry_status(row) -> str:
        if pd.isna(row["pantry_id"]):
            return "Not in pantry"

        if not can_convert_units(
            row["pantry_unit"],
            row["unit"],
        ):
            return "Pantry unit incompatible"

        if float(row["pantry_quantity"]) >= float(
            row["required_quantity"]
        ):
            return "Covered by pantry"

        if float(row["pantry_quantity"]) > 0:
            return "Partially covered"

        return "Out of stock"

    result["pantry_status"] = result.apply(
        calculate_pantry_status,
        axis=1,
    )

    result["has_package_details"] = (
        result["package_quantity"].notna()
        & result["package_unit"].notna()
        & result["package_price"].notna()
    )

    result["package_unit_matches"] = result.apply(
        lambda row: (
            bool(row["has_package_details"])
            and can_convert_units(
                row["package_unit"],
                row["unit"],
            )
        ),
        axis=1,
    )

    def package_size_in_need_unit(row) -> float:
        if not row["package_unit_matches"]:
            return 0.0

        return convert_quantity(
            quantity=float(row["package_quantity"]),
            from_unit=str(row["package_unit"]),
            to_unit=str(row["unit"]),
        )

    result[
        "package_size_in_need_unit"
    ] = result.apply(
        package_size_in_need_unit,
        axis=1,
    )

    def calculate_packages(row) -> int:
        purchase_quantity = float(
            row["purchase_quantity"]
        )

        if purchase_quantity <= 0:
            return 0

        package_size = float(
            row["package_size_in_need_unit"]
        )

        if package_size <= 0:
            return 0

        return math.ceil(
            purchase_quantity / package_size
        )

    result["packages_needed"] = result.apply(
        calculate_packages,
        axis=1,
    )

    result["purchased_quantity"] = (
        result["packages_needed"]
        * result["package_size_in_need_unit"]
    )

    result["expected_leftover"] = (
        result["purchased_quantity"]
        - result["purchase_quantity"]
    ).clip(lower=0)

    result["checkout_cost"] = (
        result["packages_needed"]
        * result["package_price"].fillna(0)
    )

    result["package_status"] = result.apply(
        lambda row: (
            "Covered by pantry"
            if float(row["purchase_quantity"]) <= 0
            else (
                "Package details missing"
                if not row["has_package_details"]
                else (
                    "Package unit incompatible"
                    if not row["package_unit_matches"]
                    else "Ready to purchase"
                )
            )
        ),
        axis=1,
    )

    return result