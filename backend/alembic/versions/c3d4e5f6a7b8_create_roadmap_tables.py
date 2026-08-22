"""create_roadmap_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. roadmaps table
    op.create_table(
        'roadmaps',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False, server_default='strict'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('source_document_id', sa.String(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_roadmaps_profile_id', 'roadmaps', ['profile_id'])
    op.create_index('ix_roadmaps_is_active', 'roadmaps', ['is_active'])

    # 2. roadmap_nodes table
    op.create_table(
        'roadmap_nodes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('roadmap_id', sa.String(), nullable=False),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('node_type', sa.String(), nullable=False, server_default='topic'),
        sa.Column('status', sa.String(), nullable=False, server_default='not_started'),
        sa.Column('parent_id', sa.String(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('mastery_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ai_generated', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('metadata_json', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['roadmap_id'], ['roadmaps.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['roadmap_nodes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_roadmap_nodes_roadmap_id', 'roadmap_nodes', ['roadmap_id'])
    op.create_index('ix_roadmap_nodes_profile_id', 'roadmap_nodes', ['profile_id'])
    op.create_index('ix_roadmap_nodes_status', 'roadmap_nodes', ['status'])
    op.create_index('ix_roadmap_nodes_parent_id', 'roadmap_nodes', ['parent_id'])

    # 3. roadmap_edges table
    op.create_table(
        'roadmap_edges',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('roadmap_id', sa.String(), nullable=False),
        sa.Column('from_node_id', sa.String(), nullable=False),
        sa.Column('to_node_id', sa.String(), nullable=False),
        sa.Column('edge_type', sa.String(), nullable=False, server_default='sequential'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['roadmap_id'], ['roadmaps.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_node_id'], ['roadmap_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_node_id'], ['roadmap_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_roadmap_edges_roadmap_id', 'roadmap_edges', ['roadmap_id'])
    op.create_index('ix_roadmap_edges_from_node_id', 'roadmap_edges', ['from_node_id'])
    op.create_index('ix_roadmap_edges_to_node_id', 'roadmap_edges', ['to_node_id'])


def downgrade() -> None:
    op.drop_index('ix_roadmap_edges_to_node_id', table_name='roadmap_edges')
    op.drop_index('ix_roadmap_edges_from_node_id', table_name='roadmap_edges')
    op.drop_index('ix_roadmap_edges_roadmap_id', table_name='roadmap_edges')
    op.drop_table('roadmap_edges')

    op.drop_index('ix_roadmap_nodes_parent_id', table_name='roadmap_nodes')
    op.drop_index('ix_roadmap_nodes_status', table_name='roadmap_nodes')
    op.drop_index('ix_roadmap_nodes_profile_id', table_name='roadmap_nodes')
    op.drop_index('ix_roadmap_nodes_roadmap_id', table_name='roadmap_nodes')
    op.drop_table('roadmap_nodes')

    op.drop_index('ix_roadmaps_is_active', table_name='roadmaps')
    op.drop_index('ix_roadmaps_profile_id', table_name='roadmaps')
    op.drop_table('roadmaps')
