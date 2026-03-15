from datetime import datetime

from sqlalchemy import DateTime, Float, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActualGeneration(Base):
    __tablename__ = "actual_generation"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    target_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, unique=True, index=True
    )
    generation_mw: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ForecastGeneration(Base):
    __tablename__ = "forecast_generation"
    __table_args__ = (UniqueConstraint("target_time", "created_at", name="uq_forecast_target_created"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    target_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    generation_mw: Mapped[float] = mapped_column(Float, nullable=False)
