"""add bridge tables

The Bridge feasibility engine's six tables (bridge-plan-v3.md): the job queue,
stored verdicts, candidate pools, the pgvector card index, per-step query-plan
templates, and the exact-request LLM/embedding cache. Also creates the pgvector
extension — the first vector-typed column in this schema.

No ANN index on bridge_dataset_cards.embedding on purpose: at this corpus size
exact scan is fast and correct; add HNSW in a later migration when it isn't.

Revision ID: a3c9e51f7d24
Revises: d4e8f1a2c9b7
Create Date: 2026-08-20

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3c9e51f7d24'
down_revision: Union[str, Sequence[str], None] = 'd4e8f1a2c9b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector must exist before any Vector column. It is NOT a trusted
    # extension (verified against 0.8.6's control file), so this statement needs
    # superuser — which CI and docker-compose have (they connect as postgres),
    # but a local dev database owned by the app role does not. IF NOT EXISTS
    # makes the pre-created case a no-op, so the fix for restricted roles is a
    # one-time, per-database superuser step:
    #     psql -d ncplusplus_dev  -c 'CREATE EXTENSION vector'
    #     psql -d ncplusplus_test -c 'CREATE EXTENSION vector'
    # (On RDS, run it once as the master user.) The except below turns the
    # otherwise-cryptic InsufficientPrivilege into that instruction.
    try:
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    except sa.exc.ProgrammingError as exc:
        raise RuntimeError(
            "Creating the pgvector extension needs a superuser and this role "
            "isn't one. Run once, as a superuser, against THIS database:\n"
            "    CREATE EXTENSION vector;\n"
            "then re-run the migration."
        ) from exc

    op.create_table(
        'bridge_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('topic_input', sa.String(length=200), nullable=False),
        sa.Column('topic_slug', sa.String(length=120), nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('stage', sa.String(length=40), nullable=True),
        sa.Column('progress', sa.JSON(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bridge_jobs_id'), 'bridge_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_bridge_jobs_user_id'), 'bridge_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_bridge_jobs_topic_slug'), 'bridge_jobs', ['topic_slug'], unique=False)
    op.create_index(op.f('ix_bridge_jobs_status'), 'bridge_jobs', ['status'], unique=False)
    # One active bridge run per user, database-enforced. Seed jobs have NULL
    # user_id and never collide (NULLs are distinct in a unique index).
    op.create_index(
        'uq_bridge_jobs_active_per_user',
        'bridge_jobs',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running')"),
        sqlite_where=sa.text("status IN ('queued','running')"),
    )

    op.create_table(
        'bridge_verdicts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('topic_slug', sa.String(length=120), nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('topic_display', sa.String(length=200), nullable=False),
        sa.Column('verdict', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('inherited_from', sa.String(length=50), nullable=True),
        sa.Column('produced_by_job', sa.Uuid(), nullable=True),
        sa.Column('last_verified', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['produced_by_job'], ['bridge_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_slug', 'model_id', name='uq_bridge_verdicts_topic_model'),
    )
    op.create_index(op.f('ix_bridge_verdicts_id'), 'bridge_verdicts', ['id'], unique=False)
    op.create_index(op.f('ix_bridge_verdicts_status'), 'bridge_verdicts', ['status'], unique=False)

    op.create_table(
        'bridge_candidate_pools',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('topic_slug', sa.String(length=120), nullable=False),
        sa.Column('modality', sa.String(length=20), nullable=False),
        sa.Column('pool', sa.JSON(), nullable=False),
        sa.Column('last_verified', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_slug', 'modality', name='uq_bridge_pools_topic_modality'),
    )
    op.create_index(op.f('ix_bridge_candidate_pools_id'), 'bridge_candidate_pools', ['id'], unique=False)

    op.create_table(
        'bridge_dataset_cards',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('dataset_id', sa.String(length=300), nullable=False),
        sa.Column('modality', sa.String(length=20), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1024), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'dataset_id', 'chunk_index', name='uq_bridge_cards_chunk'),
    )
    op.create_index(op.f('ix_bridge_dataset_cards_id'), 'bridge_dataset_cards', ['id'], unique=False)

    op.create_table(
        'bridge_query_plans',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('plan', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id'),
    )
    op.create_index(op.f('ix_bridge_query_plans_id'), 'bridge_query_plans', ['id'], unique=False)

    op.create_table(
        'bridge_llm_cache',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cache_key', sa.String(length=64), nullable=False),
        sa.Column('call_site', sa.String(length=30), nullable=False),
        sa.Column('model', sa.String(length=50), nullable=False),
        sa.Column('response', sa.JSON(), nullable=False),
        sa.Column('usage', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key'),
    )
    op.create_index(op.f('ix_bridge_llm_cache_id'), 'bridge_llm_cache', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bridge_llm_cache_id'), table_name='bridge_llm_cache')
    op.drop_table('bridge_llm_cache')
    op.drop_index(op.f('ix_bridge_query_plans_id'), table_name='bridge_query_plans')
    op.drop_table('bridge_query_plans')
    op.drop_index(op.f('ix_bridge_dataset_cards_id'), table_name='bridge_dataset_cards')
    op.drop_table('bridge_dataset_cards')
    op.drop_index(op.f('ix_bridge_candidate_pools_id'), table_name='bridge_candidate_pools')
    op.drop_table('bridge_candidate_pools')
    op.drop_index(op.f('ix_bridge_verdicts_status'), table_name='bridge_verdicts')
    op.drop_index(op.f('ix_bridge_verdicts_id'), table_name='bridge_verdicts')
    op.drop_table('bridge_verdicts')
    op.drop_index('uq_bridge_jobs_active_per_user', table_name='bridge_jobs')
    op.drop_index(op.f('ix_bridge_jobs_status'), table_name='bridge_jobs')
    op.drop_index(op.f('ix_bridge_jobs_topic_slug'), table_name='bridge_jobs')
    op.drop_index(op.f('ix_bridge_jobs_user_id'), table_name='bridge_jobs')
    op.drop_index(op.f('ix_bridge_jobs_id'), table_name='bridge_jobs')
    op.drop_table('bridge_jobs')
    # The extension is left installed: dropping it would break any other vector
    # column an admin created out-of-band, and an unused extension is harmless.
