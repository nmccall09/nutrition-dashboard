import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL was not found."
    )


EXPECTED_TABLES = {
    "app_settings",
    "recipes",
    "ingredients",
    "recipe_ingredients",
    "meal_log",
    "meal_plan",
    "pantry_inventory",
    "pantry_transactions",
    "shopping_trips",
    "shopping_trip_items",
}

EXPECTED_VIEWS = {
    "recipe_cost_summary",
}


def verify_schema() -> None:
    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:
        table_rows = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE
                table_schema = 'public'
                AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).fetchall()

        view_rows = connection.execute(
            """
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        ).fetchall()

        setting_rows = connection.execute(
            """
            SELECT
                setting_key,
                setting_value
            FROM app_settings
            ORDER BY setting_key
            """
        ).fetchall()

    actual_tables = {
        row["table_name"]
        for row in table_rows
    }

    actual_views = {
        row["table_name"]
        for row in view_rows
    }

    missing_tables = (
        EXPECTED_TABLES - actual_tables
    )

    missing_views = (
        EXPECTED_VIEWS - actual_views
    )

    print("PostgreSQL schema verification")
    print("-" * 40)

    print("\nTables found:")
    for table_name in sorted(actual_tables):
        print(f"  - {table_name}")

    print("\nViews found:")
    for view_name in sorted(actual_views):
        print(f"  - {view_name}")

    print("\nDefault settings:")
    for setting in setting_rows:
        print(
            f"  - {setting['setting_key']}: "
            f"{setting['setting_value']}"
        )

    if missing_tables:
        raise RuntimeError(
            "Missing tables: "
            + ", ".join(sorted(missing_tables))
        )

    if missing_views:
        raise RuntimeError(
            "Missing views: "
            + ", ".join(sorted(missing_views))
        )

    print("\nSchema verification passed.")


if __name__ == "__main__":
    verify_schema()