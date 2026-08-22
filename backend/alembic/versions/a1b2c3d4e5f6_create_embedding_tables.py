"""create_embedding_tables

Revision ID: a1b2c3d4e5f6
Revises: f1a4c8e6b3d2
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a4c8e6b3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chunk_embedding_queue',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('char_offset_start', sa.Integer(), nullable=True),
        sa.Column('char_offset_end', sa.Integer(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('section_title', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='queued'),
        sa.Column('retries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chunk_embedding_queue_document_id', 'chunk_embedding_queue', ['document_id'])
    op.create_index('ix_chunk_embedding_queue_status', 'chunk_embedding_queue', ['status'])

    op.create_table(
        'embedding_cache',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('embedding_model', sa.String(), nullable=False),
        sa.Column('vector_json', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_embedding_cache_content_hash', 'embedding_cache', ['content_hash'])
    op.create_index('ix_embedding_cache_embedding_model', 'embedding_cache', ['embedding_model'])


def downgrade() -> None:
    op.drop_index('ix_embedding_cache_embedding_model', table_name='embedding_cache')
    op.drop_index('ix_embedding_cache_content_hash', table_name='embedding_cache')
    op.drop_table('embedding_cache')

    op.drop_index('ix_chunk_embedding_queue_status', table_name='chunk_embedding_queue')
    op.drop_index('ix_chunk_embedding_queue_document_id', table_name='chunk_embedding_queue')
    op.drop_table('chunk_embedding_queue')
