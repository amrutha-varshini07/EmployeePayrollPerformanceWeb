import os
import sqlite3
from contextlib import contextmanager

from werkzeug.security import generate_password_hash

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Render may provide a postgres:// URL. Modern psycopg2 expects postgresql://.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

SQLITE_PATH = os.environ.get(
    "SQLITE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "employee_payroll.db")
)


def is_postgres():
    return bool(DATABASE_URL)


class SQLiteCursorWrapper:
    """Makes the existing Flask code's %s placeholders work with SQLite."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        sql = sql.replace("%s", "?")
        return self._cursor.executemany(sql, seq_of_params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class SQLiteConnectionWrapper:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return SQLiteCursorWrapper(self._connection.cursor())

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()


def get_db_connection():
    """Return a PostgreSQL connection on Render, otherwise a local SQLite connection."""

    if is_postgres():
        if psycopg2 is None:
            raise RuntimeError(
                "PostgreSQL support is missing. Add psycopg2-binary to requirements.txt."
            )
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )

    connection = sqlite3.connect(SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    return SQLiteConnectionWrapper(connection)


def _execute_schema_postgres(connection):
    cursor = connection.cursor()

    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            emp_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(150) NOT NULL,
            department VARCHAR(150) NOT NULL,
            designation VARCHAR(150) NOT NULL,
            basic_salary NUMERIC(12, 2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_records (
            id SERIAL PRIMARY KEY,
            emp_id VARCHAR(50) NOT NULL,
            pay_month VARCHAR(30) NOT NULL,
            pay_year INTEGER NOT NULL,
            basic_salary NUMERIC(12, 2) NOT NULL,
            hra NUMERIC(12, 2) NOT NULL,
            da NUMERIC(12, 2) NOT NULL,
            medical NUMERIC(12, 2) NOT NULL,
            gross_salary NUMERIC(12, 2) NOT NULL,
            pf NUMERIC(12, 2) NOT NULL,
            tax NUMERIC(12, 2) NOT NULL,
            total_deductions NUMERIC(12, 2) NOT NULL,
            net_salary NUMERIC(12, 2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS appraisals (
            id SERIAL PRIMARY KEY,
            emp_id VARCHAR(50) NOT NULL,
            productivity NUMERIC(5, 2) NOT NULL,
            quality NUMERIC(5, 2) NOT NULL,
            teamwork NUMERIC(5, 2) NOT NULL,
            attendance NUMERIC(5, 2) NOT NULL,
            overall_score NUMERIC(5, 2) NOT NULL,
            rating VARCHAR(50) NOT NULL,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    for statement in statements:
        cursor.execute(statement)

    # Seed a single default admin account only if it does not already exist.
    cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            ("admin", generate_password_hash("admin123"))
        )

    connection.commit()
    cursor.close()


def _execute_schema_sqlite(connection):
    cursor = connection.cursor()

    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            designation TEXT NOT NULL,
            basic_salary REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT NOT NULL,
            pay_month TEXT NOT NULL,
            pay_year INTEGER NOT NULL,
            basic_salary REAL NOT NULL,
            hra REAL NOT NULL,
            da REAL NOT NULL,
            medical REAL NOT NULL,
            gross_salary REAL NOT NULL,
            pf REAL NOT NULL,
            tax REAL NOT NULL,
            total_deductions REAL NOT NULL,
            net_salary REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS appraisals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT NOT NULL,
            productivity REAL NOT NULL,
            quality REAL NOT NULL,
            teamwork REAL NOT NULL,
            attendance REAL NOT NULL,
            overall_score REAL NOT NULL,
            rating TEXT NOT NULL,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    for statement in statements:
        cursor.execute(statement.replace("%s", "?"))

    cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    connection.commit()
    cursor.close()


def init_db():
    """Create all application tables and seed the default admin account."""

    connection = get_db_connection()
    try:
        if is_postgres():
            _execute_schema_postgres(connection)
        else:
            _execute_schema_sqlite(connection)
    finally:
        connection.close()
