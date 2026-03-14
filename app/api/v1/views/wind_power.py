from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.wind_power import (
    ForecastGenerationPoint,
    UpsertActualsRequest,
    UpsertForecastsRequest,
    UpsertResponse,
    WindPowerSeriesPoint,
    WindPowerSeriesResponse,
)

router = APIRouter()

_actual_generation_by_target: dict[datetime, float] = {}
_forecast_generation_by_target: dict[datetime, list[ForecastGenerationPoint]] = {}


@router.post(
    "/wind-power/actuals",
    response_model=UpsertResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest actual wind generation points (supports BMRS fields)",
)
async def upsert_actual_generation(payload: UpsertActualsRequest) -> UpsertResponse:
    for point in payload.points:
        if point.fuel_type is not None and point.fuel_type.upper() != "WIND":
            continue
        _actual_generation_by_target[point.target_time] = point.generation_mw

    return UpsertResponse(
        inserted=len(
            [
                point
                for point in payload.points
                if point.fuel_type is None or point.fuel_type.upper() == "WIND"
            ]
        ),
        total_records=len(_actual_generation_by_target),
    )


@router.post(
    "/wind-power/forecasts",
    response_model=UpsertResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest forecast generation points",
)
async def upsert_forecast_generation(payload: UpsertForecastsRequest) -> UpsertResponse:
    for point in payload.points:
        forecast_list = _forecast_generation_by_target.setdefault(point.target_time, [])
        forecast_list.append(point)

    total_records = sum(len(points) for points in _forecast_generation_by_target.values())
    return UpsertResponse(inserted=len(payload.points), total_records=total_records)


@router.get(
    "/wind-power/series",
    response_model=WindPowerSeriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get actual vs latest-eligible forecast series",
)
async def get_wind_power_series(
    start_time: datetime,
    end_time: datetime,
    horizon_hours: int = Query(default=4, ge=1, le=168),
) -> WindPowerSeriesResponse:
    if start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than or equal to end_time",
        )

    target_times = sorted(
        time
        for time in set(_actual_generation_by_target) | set(_forecast_generation_by_target)
        if start_time <= time <= end_time
    )

    points: list[WindPowerSeriesPoint] = []
    for target_time in target_times:
        actual_value = _actual_generation_by_target.get(target_time)
        forecast_candidates = _forecast_generation_by_target.get(target_time, [])
        cutoff_time = target_time - timedelta(hours=horizon_hours)

        eligible_forecast = _pick_latest_eligible_forecast(forecast_candidates, cutoff_time)

        points.append(
            WindPowerSeriesPoint(
                target_time=target_time,
                actual_generation_mw=actual_value,
                forecast_generation_mw=(
                    eligible_forecast.generation_mw if eligible_forecast else None
                ),
                forecast_created_at=eligible_forecast.created_at if eligible_forecast else None,
            )
        )

    return WindPowerSeriesResponse(
        start_time=start_time,
        end_time=end_time,
        horizon_hours=horizon_hours,
        points=points,
    )


def _pick_latest_eligible_forecast(
    forecasts: list[ForecastGenerationPoint], cutoff_time: datetime
) -> ForecastGenerationPoint | None:
    eligible = [forecast for forecast in forecasts if forecast.created_at <= cutoff_time]
    if not eligible:
        return None

    return max(eligible, key=lambda forecast: forecast.created_at)
