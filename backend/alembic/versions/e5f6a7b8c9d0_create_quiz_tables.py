"""create_quiz_tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'quiz_attempts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.Column('roadmap_node_id', sa.String(), nullable=True),
        sa.Column('mode', sa.String(), nullable=False, server_default='practice'),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('correct_count', sa.Integer(), nullable=True),
        sa.Column('time_limit_seconds', sa.Integer(), nullable=True),
        sa.Column('questions_json', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['roadmap_node_id'], ['roadmap_nodes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_quiz_attempts_profile_id', 'quiz_attempts', ['profile_id'])
    op.create_index('ix_quiz_attempts_roadmap_node_id', 'quiz_attempts', ['roadmap_node_id'])


def downgrade() -> None:
    op.drop_index('ix_quiz_attempts_roadmap_node_id', table_name='quiz_attempts')
    op.drop_index('ix_quiz_attempts_profile_id', table_name='quiz_attempts')
    op.drop_table('quiz_attempts')
