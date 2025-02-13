"""add computed field

Revision ID: a5e4b84f57bd
Revises: a9ea4734e137
Create Date: 2024-05-14 19:52:00.019877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5e4b84f57bd'
down_revision: Union[str, None] = 'a9ea4734e137'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('computed_name', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'computed_name')
    # ### end Alembic commands ###
