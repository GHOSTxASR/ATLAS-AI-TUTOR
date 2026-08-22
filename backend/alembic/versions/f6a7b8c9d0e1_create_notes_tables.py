"""create notes tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-19 19:35:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("profile_id", sa.String(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("roadmap_node_id", sa.String(), sa.ForeignKey("roadmap_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("note_type", sa.String(), nullable=False, server_default="lesson_note"),
        sa.Column("source", sa.String(), nullable=False, server_default="ai_generated"),
        sa.Column("tags_json", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notes_profile_id", "notes", ["profile_id"])
    op.create_index("ix_notes_roadmap_node_id", "notes", ["roadmap_node_id"])
    op.create_index("ix_notes_title", "notes", ["title"])
    op.create_index("ix_notes_note_type", "notes", ["note_type"])
    op.create_index("ix_notes_created_at", "notes", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notes_created_at", table_name="notes")
    op.drop_index("ix_notes_note_type", table_name="notes")
    op.drop_index("ix_notes_title", table_name="notes")
    op.drop_index("ix_notes_roadmap_node_id", table_name="notes")
    op.drop_index("ix_notes_profile_id", table_name="notes")
    op.drop_table("notes")
