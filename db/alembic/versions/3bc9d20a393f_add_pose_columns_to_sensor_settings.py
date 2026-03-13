"""add pose columns to sensor settings

Revision ID: 3bc9d20a393f
Revises: c0661a3a1287
Create Date: 2025-11-13 17:18:06.708760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3bc9d20a393f'
down_revision: Union[str, Sequence[str], None] = 'c0661a3a1287'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    def has_column(table_name: str, column_name: str) -> bool:
        """Check if a column exists on the given table for the current dialect."""
        # SQLite: use PRAGMA table_info
        if bind.dialect.name == 'sqlite':
            result = bind.execute(sa.text(f"PRAGMA table_info('{table_name}')"))
            return any(row[1] == column_name for row in result)
        # Other dialects: use SQLAlchemy inspector
        inspector = sa.inspect(bind)
        cols = inspector.get_columns(table_name)
        return any(c.get('name') == column_name for c in cols)

    # Add columns only if they don't already exist (idempotent upgrade for SQLite non-transactional DDL)
    if not has_column('sensor_settings', 'pose_file_path'):
        op.add_column('sensor_settings', sa.Column('pose_file_path', sa.Text(), nullable=True))

    if not has_column('sensor_settings', 'status_pose'):
        op.add_column(
            'sensor_settings',
            sa.Column('status_pose', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
        )
        # Attempt to drop server_default to align ORM default-only expectation.
        # Some SQLite versions may not support altering defaults; ignore if not supported.
        try:
            op.alter_column('sensor_settings', 'status_pose', server_default=None)
        except Exception:
            pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sensor_settings', 'status_pose')
    op.drop_column('sensor_settings', 'pose_file_path')
