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


TABLES = [
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
]


def check_counts() -> None:
    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:
        print("PostgreSQL row counts")
        print("-" * 30)

        for table_name in TABLES:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS row_count
                FROM {table_name}
                """
            ).fetchone()

            print(
                f"{table_name}: "
                f"{row['row_count']:,}"
            )


if __name__ == "__main__":
    check_counts()