"""
Add events and hours_overrides tables.

Revision ID: 0006
Revises:     0005
Create Date: 2026-06-28

events
    One row per scheduled event (concert, happy hour, pop-up, etc.).
    Agent generates and posts a promo on event_date at post_time.

hours_overrides
    One row per hours change or closure notice.
    e.g. "Closed Monday July 4th" or "New hours starting next week"
    Agent posts the announcement on post_date at post_time.
    override_type: 'closure' | 'hours_change' | 'holiday' | 'general'
"""

from alembic import op
import sqlalchemy as sa

revision      = '0006'
down_revision = '0005'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # -- events ----------------------------------------------------------
    op.create_table(
        'events',
        sa.Column('id',              sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',         sa.Text(),    nullable=False),
        sa.Column('title',           sa.Text(),    nullable=False),
        sa.Column('description',     sa.Text(),    nullable=True),
        sa.Column('event_date',      sa.Text(),    nullable=False),   # YYYY-MM-DD
        sa.Column('event_end_date',  sa.Text(),    nullable=True),    # YYYY-MM-DD (multi-day)
        sa.Column('post_date',       sa.Text(),    nullable=False),   # when to post promo
        sa.Column('post_time',       sa.Text(),    nullable=False),   # HH:MM UTC
        sa.Column('event_type',      sa.Text(),    nullable=True,  server_default='event'),
        sa.Column('platforms',       sa.Text(),    nullable=True),    # JSON array
        sa.Column('tone',            sa.Text(),    nullable=True,  server_default='hype'),
        sa.Column('image_url',       sa.Text(),    nullable=True),
        sa.Column('ticket_url',      sa.Text(),    nullable=True),
        sa.Column('status',          sa.Text(),    nullable=True,  server_default='pending'),
        sa.Column('post_history_id', sa.Integer(), nullable=True),
        sa.Column('created_at',      sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
        sa.Column('updated_at',      sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
    )
    op.create_index('idx_events_user',   'events', ['user_id'])
    op.create_index('idx_events_date',   'events', ['post_date'])
    op.create_index('idx_events_status', 'events', ['status'])

    # -- hours_overrides -------------------------------------------------
    op.create_table(
        'hours_overrides',
        sa.Column('id',              sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',         sa.Text(),    nullable=False),
        sa.Column('title',           sa.Text(),    nullable=False),   # e.g. "Closed July 4th"
        sa.Column('message',         sa.Text(),    nullable=True),    # extra detail for AI
        sa.Column('override_type',   sa.Text(),    nullable=True,  server_default='closure'),
        sa.Column('post_date',       sa.Text(),    nullable=False),   # YYYY-MM-DD
        sa.Column('post_time',       sa.Text(),    nullable=False),   # HH:MM UTC
        sa.Column('platforms',       sa.Text(),    nullable=True),    # JSON array
        sa.Column('tone',            sa.Text(),    nullable=True,  server_default='friendly'),
        sa.Column('status',          sa.Text(),    nullable=True,  server_default='pending'),
        sa.Column('post_history_id', sa.Integer(), nullable=True),
        sa.Column('created_at',      sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
        sa.Column('updated_at',      sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
    )
    op.create_index('idx_hours_user',   'hours_overrides', ['user_id'])
    op.create_index('idx_hours_date',   'hours_overrides', ['post_date'])
    op.create_index('idx_hours_status', 'hours_overrides', ['status'])


def downgrade() -> None:
    op.drop_index('idx_hours_status', table_name='hours_overrides')
    op.drop_index('idx_hours_date',   table_name='hours_overrides')
    op.drop_index('idx_hours_user',   table_name='hours_overrides')
    op.drop_table('hours_overrides')

    op.drop_index('idx_events_status', table_name='events')
    op.drop_index('idx_events_date',   table_name='events')
    op.drop_index('idx_events_user',   table_name='events')
    op.drop_table('events')
