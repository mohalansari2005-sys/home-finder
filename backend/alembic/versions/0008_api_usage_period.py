"""api_usage.month -> period (YYYY-MM or YYYY-MM-DD) so TomTom requests can be counted per day too

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-13 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("api_usage", "month", new_column_name="period", type_=sa.String(10),
                    existing_type=sa.String(7), existing_nullable=False)
    op.execute("DELETE FROM api_usage WHERE provider = 'google'")  # Google Maps Platform is no longer used


def downgrade() -> None:
    op.execute("DELETE FROM api_usage WHERE length(period) > 7")
    op.alter_column("api_usage", "period", new_column_name="month", type_=sa.String(7),
                    existing_type=sa.String(10), existing_nullable=False)
