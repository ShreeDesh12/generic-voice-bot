"""add title version is_active to bots

Revision ID: 71e2094110c3
Revises: 6b654e58d8bb
Create Date: 2026-04-13 13:37:39.911201

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '71e2094110c3'
down_revision: Union[str, Sequence[str], None] = '6b654e58d8bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _has_column("bots", "title"):
        op.add_column('bots', sa.Column('title', sa.String(length=255), nullable=True))
    if not _has_column("bots", "version"):
        op.add_column('bots', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    if not _has_column("bots", "is_active"):
        op.add_column('bots', sa.Column('is_active', sa.String(length=10), nullable=False, server_default='active'))


def downgrade() -> None:
    if _has_column("bots", "is_active"):
        op.drop_column('bots', 'is_active')
    if _has_column("bots", "version"):
        op.drop_column('bots', 'version')
    if _has_column("bots", "title"):
        op.drop_column('bots', 'title')
