"""add caller_user_id to contacts

Revision ID: 6b654e58d8bb
Revises: db4ee961465b
Create Date: 2026-04-13 12:44:49.898873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b654e58d8bb'
down_revision: Union[str, Sequence[str], None] = 'db4ee961465b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contacts', sa.Column('caller_user_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_contacts_caller_user_id', 'contacts', 'users',
        ['caller_user_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('bots', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('bots', 'deleted_at')
    op.drop_constraint('fk_contacts_caller_user_id', 'contacts', type_='foreignkey')
    op.drop_column('contacts', 'caller_user_id')
