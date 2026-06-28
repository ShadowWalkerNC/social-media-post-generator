"""
Add specials table -- user-defined weekly schedule for the AutomationAgent.

Revision ID: 0005
Revises:     0004
Create Date: 2026-06-28

Each row represents one scheduled post the agent should generate and publish.
The user fills this table via the /schedule page. The AutomationAgent reads it
every hour and creates post_history rows for any specials that are due today
and haven't been queued yet.

Schema:
    specials
        id             INTEGER  PRIMARY KEY AUTOINCREMENT
        user_id        TEXT     NOT NULL  -- FK to users.id
        item_name      TEXT     NOT NULL  -- e.g. "Truffle Burger"
        description    TEXT               -- optional longer description / keywords for AI
        post_date      TEXT     NOT NULL  -- YYYY-MM-DD  (which day to post)
        post_time      TEXT     NOT NULL  -- HH:MM 24h UTC (e.g. "11:00")
        platforms      TEXT               -- JSON array e.g. ["fb","ig","tt"]
        content_type   TEXT     DEFAULT 'daily_special'  -- daily_special | location | general
        tone           TEXT     DEFAULT 'friendly'
        image_url      TEXT               -- optional image URL to attach
        status         TEXT     DEFAULT 'pending'  -- pending | queued | published | cancelled
        post_history_id INTEGER           -- FK to post_history.id once queued
        created_at     INTEGER
        updated_at     INTEGER

Applying:
    alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa

revision      = '0005'
down_revision = '0004'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        'specials',
        sa.Column('id',              sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',         sa.Text(),    nullable=False),
        sa.Column('item_name',       sa.Text(),    nullable=False),
        sa.Column('description',     sa.Text(),    nullable=True),
        sa.Column('post_date',       sa.Text(),    nullable=False),   # YYYY-MM-DD
        sa.Column('post_time',       sa.Text(),    nullable=False),   # HH:MM
        sa.Column('platforms',       sa.Text(),    nullable=True),    # JSON array
        sa.Column('content_type',    sa.Text(),    nullable=True,  server_default='daily_special'),
        sa.Column('tone',            sa.Text(),    nullable=True,  server_default='friendly'),
        sa.Column('image_url',       sa.Text(),    nullable=True),
        sa.Column('status',          sa.Text(),    nullable=True,  server_default='pending'),
        sa.Column('post_history_id', sa.Integer(), nullable=True),
        sa.Column('created_at',      sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
        sa.Column('updated_at',      sa.Integer(), nullable=True,
                  server_default=sa.text("(strftime('%s','now'))")),
    )
    op.create_index('idx_specials_user',    'specials', ['user_id'])
    op.create_index('idx_specials_date',    'specials', ['post_date'])
    op.create_index('idx_specials_status',  'specials', ['status'])


def downgrade() -> None:
    op.drop_index('idx_specials_status', table_name='specials')
    op.drop_index('idx_specials_date',   table_name='specials')
    op.drop_index('idx_specials_user',   table_name='specials')
    op.drop_table('specials')
