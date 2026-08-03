from database.connection import get_connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipes (
    recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_name TEXT NOT NULL UNIQUE,
    meal_type TEXT NOT NULL CHECK (
        meal_type IN ('Breakfast', 'Lunch', 'Dinner', 'Snack')
    ),
    servings REAL NOT NULL DEFAULT 1 CHECK (servings > 0),
    calories_per_serving REAL NOT NULL CHECK (
        calories_per_serving >= 0
    ),
    protein_per_serving REAL NOT NULL CHECK (
        protein_per_serving >= 0
    ),
    carbs_per_serving REAL NOT NULL DEFAULT 0 CHECK (
        carbs_per_serving >= 0
    ),
    fat_per_serving REAL NOT NULL DEFAULT 0 CHECK (
        fat_per_serving >= 0
    ),
    prep_minutes INTEGER CHECK (
        prep_minutes >= 0
    ),
    estimated_cost_per_serving REAL CHECK (
        estimated_cost_per_serving >= 0
    ),
    instructions TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category TEXT NOT NULL,
    preferred_store TEXT NOT NULL CHECK (
        preferred_store IN ('Aldi', 'Costco', 'Other')
    ),
    default_unit TEXT NOT NULL,
    estimated_unit_cost REAL NOT NULL DEFAULT 0 CHECK (
        estimated_unit_cost >= 0
    ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL,
    estimated_cost REAL NOT NULL DEFAULT 0 CHECK (
        estimated_cost >= 0
    ),
    FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON DELETE RESTRICT,
    UNIQUE (recipe_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS meal_log (
    meal_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_date TEXT NOT NULL,
    meal_type TEXT NOT NULL CHECK (
        meal_type IN ('Breakfast', 'Lunch', 'Dinner', 'Snack')
    ),
    recipe_id INTEGER NOT NULL,
    servings REAL NOT NULL DEFAULT 1 CHECK (
        servings > 0
    ),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS meal_plan (
    meal_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_date TEXT NOT NULL,
    meal_type TEXT NOT NULL CHECK (
        meal_type IN ('Breakfast', 'Lunch', 'Dinner', 'Snack')
    ),
    recipe_id INTEGER NOT NULL,
    servings REAL NOT NULL DEFAULT 1 CHECK (
        servings > 0
    ),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recipe_id)
        REFERENCES recipes(recipe_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pantry_inventory (
    pantry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL UNIQUE,
    quantity_on_hand REAL NOT NULL DEFAULT 0 CHECK (
        quantity_on_hand >= 0
    ),
    unit TEXT NOT NULL,
    minimum_quantity REAL NOT NULL DEFAULT 0 CHECK (
        minimum_quantity >= 0
    ),
    expiration_date TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pantry_transactions (
    pantry_transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pantry_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    meal_log_id INTEGER,
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN (
            'Meal deduction',
            'Meal restoration',
            'Manual adjustment',
            'Purchase'
        )
    ),
    quantity_change REAL NOT NULL,
    unit TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pantry_id)
        REFERENCES pantry_inventory(pantry_id)
        ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON DELETE CASCADE,
    FOREIGN KEY (meal_log_id)
        REFERENCES meal_log(meal_log_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS shopping_trips (
    shopping_trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (
        status IN ('Open', 'Completed')
    ),
    estimated_checkout_cost REAL NOT NULL DEFAULT 0,
    actual_total_cost REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS shopping_trip_items (
    shopping_trip_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shopping_trip_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,

    required_quantity REAL NOT NULL DEFAULT 0,
    need_to_buy_quantity REAL NOT NULL DEFAULT 0,
    need_unit TEXT NOT NULL,

    package_quantity REAL,
    package_unit TEXT,
    packages_planned INTEGER NOT NULL DEFAULT 0,
    planned_purchase_quantity REAL NOT NULL DEFAULT 0,
    estimated_checkout_cost REAL NOT NULL DEFAULT 0,

    preferred_store TEXT,

    purchased INTEGER NOT NULL DEFAULT 0 CHECK (
        purchased IN (0, 1)
    ),
    actual_quantity REAL,
    actual_unit TEXT,
    actual_price REAL,
    actual_store TEXT,

    pantry_added INTEGER NOT NULL DEFAULT 0 CHECK (
        pantry_added IN (0, 1)
    ),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (shopping_trip_id)
        REFERENCES shopping_trips(shopping_trip_id)
        ON DELETE CASCADE,

    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id)
        ON DELETE RESTRICT
);

CREATE VIEW IF NOT EXISTS recipe_cost_summary AS
SELECT
    r.recipe_id,

    COUNT(ri.recipe_ingredient_id) AS ingredient_count,

    COALESCE(
        SUM(ri.estimated_cost),
        0
    ) AS total_ingredient_cost,

    CASE
        WHEN COUNT(ri.recipe_ingredient_id) > 0
            THEN COALESCE(
                SUM(ri.estimated_cost),
                0
            ) / r.servings

        ELSE COALESCE(
            r.estimated_cost_per_serving,
            0
        )
    END AS effective_cost_per_serving

FROM recipes AS r

LEFT JOIN recipe_ingredients AS ri
    ON r.recipe_id = ri.recipe_id

GROUP BY
    r.recipe_id,
    r.servings,
    r.estimated_cost_per_serving;
"""


DEFAULT_SETTINGS = {
    "daily_protein_goal": "180",
    "daily_calorie_goal": "2200",
    "weekly_grocery_budget": "100",
}

def add_column_if_missing(
    connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """
    Add a column to an existing SQLite table if it does not exist.
    """
    columns = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    existing_columns = {
        column["name"]
        for column in columns
    }

    if column_name not in existing_columns:
        connection.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_definition}
            """
        )


def initialize_database() -> None:
    """
    Create database objects and apply lightweight migrations.
    """
    with get_connection() as connection:
        connection.executescript(SCHEMA_SQL)

        add_column_if_missing(
            connection=connection,
            table_name="meal_log",
            column_name="calories_snapshot",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="meal_log",
            column_name="protein_snapshot",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="meal_log",
            column_name="carbs_snapshot",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="meal_log",
            column_name="fat_snapshot",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="meal_log",
            column_name="cost_snapshot",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="meal_plan",
            column_name="is_logged",
            column_definition="INTEGER NOT NULL DEFAULT 0",
        )

        add_column_if_missing(
            connection=connection,
            table_name="meal_log",
            column_name="pantry_deducted",
            column_definition="INTEGER NOT NULL DEFAULT 0",
        )

        add_column_if_missing(
            connection=connection,
            table_name="ingredients",
            column_name="package_quantity",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="ingredients",
            column_name="package_unit",
            column_definition="TEXT",
        )

        add_column_if_missing(
            connection=connection,
            table_name="ingredients",
            column_name="package_price",
            column_definition="REAL",
        )

        add_column_if_missing(
            connection=connection,
            table_name="ingredients",
            column_name="package_description",
            column_definition="TEXT",
        )

        add_column_if_missing(
            connection=connection,
            table_name="ingredients",
            column_name="is_active",
            column_definition="INTEGER NOT NULL DEFAULT 1",
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO app_settings (
                setting_key,
                setting_value
            )
            VALUES (%s, %s)
            """,
            DEFAULT_SETTINGS.items(),
        )

        connection.commit()


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")