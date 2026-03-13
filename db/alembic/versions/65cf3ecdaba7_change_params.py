"""change params

Revision ID: 65cf3ecdaba7
Revises: b7263ddcafbf
Create Date: 2025-11-07 09:59:45.514740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65cf3ecdaba7'
down_revision: Union[str, Sequence[str], None] = 'b7263ddcafbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # work_configs modifications
    with op.batch_alter_table('work_configs', schema=None) as batch:
        batch.drop_column('mask_minimal_area')
        batch.drop_column('skip_frame')
        batch.drop_column('mask_img_thresh_1')
        batch.alter_column(
            'mask_img_thresh_2',
            new_column_name='seg_threshold',
            existing_type=sa.Integer(),
            nullable=False
        )
        batch.add_column(sa.Column('seg_kernel_size', sa.Integer(), nullable=False, server_default='5'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('work_configs', schema=None) as batch:
        batch.alter_column(
            'seg_threshold',
            new_column_name='mask_img_thresh_2',
            existing_type=sa.Integer(),
            nullable=False
        )
        batch.add_column(sa.Column('mask_img_thresh_1', sa.Integer(), nullable=False, server_default='50'))
        batch.add_column(sa.Column('mask_minimal_area', sa.Integer(), nullable=False, server_default='200'))
        batch.add_column(sa.Column('skip_frame', sa.Integer(), nullable=True, server_default='0'))
        batch.drop_column('seg_kernel_size')