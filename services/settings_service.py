from database.connection import get_connection


DEFAULT_SETTINGS = {
    "daily_protein_goal": 180.0,
    "daily_calorie_goal": 2200.0,
    "weekly_grocery_budget": 100.0,
}


def get_setting(
    setting_key: str,
    default_value: float,
) -> float:
    query = """
        SELECT setting_value
        FROM app_settings
        WHERE setting_key = %s
    """

    with get_connection() as connection:
        row = connection.execute(
            query,
            (setting_key,),
        ).fetchone()

    if row is None:
        return default_value

    try:
        return float(row["setting_value"])
    except (TypeError, ValueError):
        return default_value


def get_all_settings() -> dict[str, float]:
    return {
        setting_key: get_setting(
            setting_key,
            default_value,
        )
        for setting_key, default_value
        in DEFAULT_SETTINGS.items()
    }


def update_setting(
    setting_key: str,
    setting_value: float,
) -> None:
    query = """
        INSERT INTO app_settings (
            setting_key,
            setting_value
        )
        VALUES (%s, %s)

        ON CONFLICT (setting_key)
        DO UPDATE SET
            setting_value = EXCLUDED.setting_value
    """

    with get_connection() as connection:
        connection.execute(
            query,
            (
                setting_key,
                str(setting_value),
            ),
        )

        connection.commit()


def update_nutrition_settings(
    daily_protein_goal: float,
    daily_calorie_goal: float,
    weekly_grocery_budget: float,
) -> None:
    settings = {
        "daily_protein_goal": daily_protein_goal,
        "daily_calorie_goal": daily_calorie_goal,
        "weekly_grocery_budget": weekly_grocery_budget,
    }

    rows = [
        (
            setting_key,
            str(setting_value),
        )
        for setting_key, setting_value
        in settings.items()
    ]

    query = """
        INSERT INTO app_settings (
            setting_key,
            setting_value
        )
        VALUES (%s, %s)

        ON CONFLICT (setting_key)
        DO UPDATE SET
            setting_value = EXCLUDED.setting_value
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                query,
                rows,
            )

        connection.commit()