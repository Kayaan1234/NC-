"""add email_outbox

Durable queue for transactional emails (verification, password reset, account
notices), drained by a thread in the worker process. Replaces the previous
in-process FastAPI BackgroundTask sends, which were lost if an instance recycled
between the HTTP response and the send.

Revision ID: d4e8f1a2c9b7
Revises: b506bae6b968
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8f1a2c9b7'
down_revision: Union[str, Sequence[str], None] = 'b506bae6b968'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'email_outbox',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email_type', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.String(length=2000), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_outbox_id'), 'email_outbox', ['id'], unique=False)
    # Serves the claim hot path: status='queued' AND next_attempt_at <= now.
    op.create_index('ix_email_outbox_claim', 'email_outbox', ['status', 'next_attempt_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_email_outbox_claim', table_name='email_outbox')
    op.drop_index(op.f('ix_email_outbox_id'), table_name='email_outbox')
    op.drop_table('email_outbox')
