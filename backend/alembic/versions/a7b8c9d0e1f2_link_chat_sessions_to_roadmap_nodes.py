"""link chat sessions to roadmap nodes

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-25

Chat threads had no idea which roadmap topic they belonged to, so opening the
tutor from a topic started a fresh thread every time and nothing studied in a
chat could be reflected back onto the roadmap.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table because SQLite cannot add a foreign key in place.
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(sa.Column("roadmap_node_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_chat_sessions_roadmap_node_id",
            "roadmap_nodes",
            ["roadmap_node_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_chat_sessions_roadmap_node_id", "chat_sessions", ["roadmap_node_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_roadmap_node_id", table_name="chat_sessions")
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_constraint("fk_chat_sessions_roadmap_node_id", type_="foreignkey")
        batch.drop_column("roadmap_node_id")
