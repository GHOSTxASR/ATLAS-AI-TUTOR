"""initial_schema

Revision ID: 8ba7e3269dd6
Revises: 
Create Date: 2026-06-14 18:03:02.785667

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '8ba7e3269dd6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Base revision; schema creation starts in later migrations."""
    return None


def downgrade() -> None:
    """Base revision has no schema changes to roll back."""
    return None
