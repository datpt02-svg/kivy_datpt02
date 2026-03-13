"""merge multiple heads

Revision ID: c0661a3a1287
Revises: 17bd5ebc9b02, 61fb7cd2034a
Create Date: 2025-11-07 15:32:53.283156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0661a3a1287'
down_revision: Union[str, Sequence[str], None] = ('17bd5ebc9b02', '61fb7cd2034a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
