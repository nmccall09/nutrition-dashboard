import os
from typing import Any, Sequence

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.rows import dict_row


load_dotenv()


def get_database_url() -> str:
    """
    Read the database URL locally from .env or from
    Streamlit Community Cloud secrets.
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return database_url

    try:
        database_url = st.secrets["DATABASE_URL"]
    except (KeyError, FileNotFoundError):
        database_url = None

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL was not found in the environment "
            "or Streamlit secrets."
        )

    return str(database_url)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(
        get_database_url(),
        row_factory=dict_row,
        connect_timeout=10,
    )


def query_dataframe(
    query: str,
    params: Sequence[Any] | None = None,
) -> pd.DataFrame:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                params,
            )

            rows = cursor.fetchall()

            columns = [
                column.name
                for column in cursor.description
            ]

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows)