"""create games table

Revision ID: 0001_create_games
Revises:
Create Date: 2026-11-12 04:55:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_games"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
    )
    op.create_index(op.f("ix_games_game_id"), "games", ["game_id"], unique=True)
    op.create_index(op.f("ix_games_status"), "games", ["status"], unique=False)
    op.create_index(op.f("ix_games_winner_id"), "games", ["winner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_winner_id"), table_name="games")
    op.drop_index(op.f("ix_games_status"), table_name="games")
    op.drop_index(op.f("ix_games_game_id"), table_name="games")
    op.drop_table("games")
