import os
import psycopg
from dotenv import load_dotenv
from contextlib import contextmanager
import streamlit as st


def create_connection_string():
    """Create PostgreSQL connection string from environment variables"""
    load_dotenv()

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB")

    # Validate required fields
    if not all([user, password, database]):
        raise ValueError(
            "Missing required environment variables: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB"
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def create_connection():
    """Create a new database connection (for CLI usage)"""
    conn_str = create_connection_string()
    print(conn_str)

    try:
        conn = psycopg.connect(conn_str)
        return conn
    except Exception as e:
        raise ConnectionError(f"Failed to connect to database: {e}")


@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = create_connection()
        yield conn
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


@st.cache_resource
def init_connection():
    """Cached connection for Streamlit app"""
    conn_str = create_connection_string()

    try:
        conn = psycopg.connect(conn_str)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        raise


def read_query_from_sql_file(SQL_FILE):
    with open(SQL_FILE, "r", encoding="utf-8") as file:
        sql_query = file.read()

    return sql_query


def format_db_response(data, columns):
    response = []

    for row in data:
        response.append(dict(zip(columns, row)))

    return response
