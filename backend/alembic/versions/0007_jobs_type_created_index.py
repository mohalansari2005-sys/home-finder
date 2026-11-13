"""jobs (type, created_at) index for the scheduler's per-source max(created_at) scan

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13 21:00:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_jobs_type_created", "jobs", ["type", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_type_created", table_name="jobs")
