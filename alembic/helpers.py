"""Shared helpers for alembic migrations."""
from alembic import op
from sqlalchemy import inspect


def has_column(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def has_table(table: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()
