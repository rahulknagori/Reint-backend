from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field


class ActualGenerationPoint(BaseModel):
    target_time: datetime = Field(
        validation_alias=AliasChoices("target_time", "startTime"),
    )
    generation_mw: float = Field(
        ge=0,
        validation_alias=AliasChoices("generation_mw", "generation"),
    )
    fuel_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("fuel_type", "fuelType"),
    )


class ForecastGenerationPoint(BaseModel):
    target_time: datetime
    created_at: datetime
    generation_mw: float = Field(ge=0)


class UpsertActualsRequest(BaseModel):
    points: list[ActualGenerationPoint]


class UpsertForecastsRequest(BaseModel):
    points: list[ForecastGenerationPoint]


class UpsertResponse(BaseModel):
    inserted: int
    total_records: int


class WindPowerSeriesPoint(BaseModel):
    target_time: datetime
    actual_generation_mw: float | None = None
    forecast_generation_mw: float | None = None
    forecast_created_at: datetime | None = None


class WindPowerSeriesResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    horizon_hours: int
    points: list[WindPowerSeriesPoint]
