"""create wind generation tables

Revision ID: 202603150001
Revises:
Create Date: 2026-03-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202603150001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actual_generation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation_mw", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actual_generation_target_time", "actual_generation", ["target_time"], unique=True)

    op.create_table(
        "forecast_generation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation_mw", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_time", "created_at", name="uq_forecast_target_created"),
    )
    op.create_index("ix_forecast_generation_created_at", "forecast_generation", ["created_at"], unique=False)
    op.create_index("ix_forecast_generation_target_time", "forecast_generation", ["target_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_forecast_generation_target_time", table_name="forecast_generation")
    op.drop_index("ix_forecast_generation_created_at", table_name="forecast_generation")
    op.drop_table("forecast_generation")
    op.drop_index("ix_actual_generation_target_time", table_name="actual_generation")
    op.drop_table("actual_generation")
