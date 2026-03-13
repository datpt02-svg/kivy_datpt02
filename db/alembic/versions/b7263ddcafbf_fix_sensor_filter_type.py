"""fix sensor_filter type

Revision ID: b7263ddcafbf
Revises: f80a47f11ff1
Create Date: 2025-09-22 10:43:39.870958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = 'b7263ddcafbf'
down_revision: Union[str, Sequence[str], None] = 'f80a47f11ff1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create a session bound to Alembic connection
    bind = op.get_bind()
    session = Session(bind=bind)

    # 2. Migrate data
    mapping = {
        "None": 0,
        "STC": 1,
        "Trail": 2
    }

    result = session.execute(sa.text("SELECT id, sensor_filter FROM work_configs"))
    migrated_count = 0
    for row in result:
        value = row.sensor_filter
        if isinstance(value, str):
            new_value = mapping.get(value, 0)
        elif value is None:
            new_value = 0
        else:
            new_value = value  # already integer

        if new_value != value:
            session.execute(
                sa.text("UPDATE work_configs SET sensor_filter = :new_value WHERE id = :id"),
                {"new_value": new_value, "id": row.id}
            )
            migrated_count += 1

    session.commit()
    print(f"INFO [alembic.runtime.migration] Successfully migrated sensor_filter column for {migrated_count} entries.")


def downgrade() -> None:
    """Downgrade schema."""

    # 1. Convert integer values back to strings
    bind = op.get_bind()
    session = Session(bind=bind)

    reverse_mapping = {
        0: "None",
        1: "STC",
        2: "Trail"
    }

    result = session.execute(sa.text("SELECT id, sensor_filter FROM work_configs"))
    reverted_count = 0
    for row in result:
        value = row.sensor_filter
        if isinstance(value, int):
            new_value = reverse_mapping.get(value, "None")
            session.execute(
                sa.text("UPDATE work_configs SET sensor_filter = :new_value WHERE id = :id"),
                {"new_value": new_value, "id": row.id}
            )
            reverted_count += 1

    session.commit()
    print(f"INFO [alembic.runtime.migration] Reverted sensor_filter column for {reverted_count} entries.")