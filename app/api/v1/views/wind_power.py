import asyncio
import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.response import build_success_response
from app.db.models import ActualGeneration, ForecastGeneration
from app.db.session import SessionLocal
from app.schemas.api_response import ApiResponse
from app.schemas.wind_power import (
    ActualGenerationPoint,
    ForecastGenerationPoint,
    UpsertResponse,
    WindPowerSeriesPoint,
    WindPowerSeriesResponse,
)

router = APIRouter()
_BMRS_FUELHH_STREAM_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"
_BMRS_WINDFOR_STREAM_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"
_JAN_2024_START = datetime.fromisoformat("2024-01-01T00:00:00+00:00")
_JAN_2024_END = datetime.fromisoformat("2024-01-31T23:30:00+00:00")
_JAN_2024_PUBLISH_FROM = datetime.fromisoformat("2023-12-30T00:00:00+00:00")
_JAN_2024_PUBLISH_TO = datetime.fromisoformat("2024-01-31T23:59:59+00:00")


@router.post(
    "/wind-power/sync-bmrs",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch and ingest Jan-2024 actuals + forecasts from BMRS",
)
async def sync_jan_2024_wind_data(
    request: Request,
    reset_existing: bool = Query(default=True, description="Clear existing DB rows before sync"),
) -> ApiResponse:
    if reset_existing:
        _reset_tables()

    actual_query_params: dict[str, str | list[str]] = {
        "settlementDateFrom": "2024-01-01",
        "settlementDateTo": "2024-01-31",
        "fuelType": ["WIND"],
    }
    actual_rows = await asyncio.to_thread(
        _fetch_bmrs_rows, _BMRS_FUELHH_STREAM_URL, actual_query_params
    )
    actual_points = _parse_actual_points(actual_rows)
    actual_inserted = _store_actual_points(actual_points)

    forecast_query_params: dict[str, str | list[str]] = {
        "publishDateTimeFrom": _JAN_2024_PUBLISH_FROM.isoformat(),
        "publishDateTimeTo": _JAN_2024_PUBLISH_TO.isoformat(),
    }
    forecast_rows = await asyncio.to_thread(
        _fetch_bmrs_rows, _BMRS_WINDFOR_STREAM_URL, forecast_query_params
    )
    forecast_points = _parse_forecast_points(forecast_rows)
    forecast_inserted = _store_forecast_points(
        forecast_points,
        start_time=_JAN_2024_START,
        end_time=_JAN_2024_END,
        horizon_min_hours=0,
        horizon_max_hours=48,
    )

    payload = UpsertResponse(
        inserted=actual_inserted + forecast_inserted,
        total_records=_count_total_records(),
    )
    return ApiResponse.model_validate(
        build_success_response(
            request,
            data=payload.model_dump(),
            status_code=status.HTTP_200_OK,
            message="BMRS wind data synced successfully",
        )
    )


@router.get(
    "/wind-power/series",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Get actual vs latest-eligible forecast series",
)
async def get_wind_power_series(
    request: Request,
    start_time: datetime,
    end_time: datetime,
    horizon_hours: int = Query(default=4, ge=0, le=48),
) -> ApiResponse:
    if start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than or equal to end_time",
        )
    if start_time < _JAN_2024_START or end_time > _JAN_2024_END:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only January 2024 data is available.",
        )

    actual_by_target, forecasts_by_target = _load_series_data_from_db(start_time, end_time)
    target_times = sorted(set(actual_by_target) | set(forecasts_by_target))

    points: list[WindPowerSeriesPoint] = []
    for target_time in target_times:
        actual_value = actual_by_target.get(target_time)
        forecast_candidates = forecasts_by_target.get(target_time, [])
        cutoff_time = target_time - timedelta(hours=horizon_hours)

        eligible_forecast = _pick_latest_eligible_forecast(forecast_candidates, cutoff_time)

        points.append(
            WindPowerSeriesPoint(
                target_time=target_time,
                actual_generation_mw=actual_value,
                forecast_generation_mw=eligible_forecast[1] if eligible_forecast else None,
                forecast_created_at=eligible_forecast[0] if eligible_forecast else None,
            )
        )

    payload = WindPowerSeriesResponse(
        start_time=start_time,
        end_time=end_time,
        horizon_hours=horizon_hours,
        points=points,
    )
    return ApiResponse.model_validate(
        build_success_response(
            request,
            data=payload.model_dump(),
            status_code=status.HTTP_200_OK,
            message="Wind power series fetched successfully",
        )
    )


def _pick_latest_eligible_forecast(
    forecasts: list[tuple[datetime, float]], cutoff_time: datetime
) -> tuple[datetime, float] | None:
    for created_at, generation_mw in forecasts:
        if created_at <= cutoff_time:
            return (created_at, generation_mw)
    return None


def _store_actual_points(points: list[ActualGenerationPoint]) -> int:
    valid_rows = [
        {"target_time": point.target_time, "generation_mw": point.generation_mw}
        for point in points
        if point.fuel_type is None or point.fuel_type.upper() == "WIND"
    ]
    if not valid_rows:
        return 0

    with SessionLocal.begin() as session:
        stmt = insert(ActualGeneration).values(valid_rows)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[ActualGeneration.target_time],
            set_={"generation_mw": stmt.excluded.generation_mw},
        )
        session.execute(upsert_stmt)

    return len(valid_rows)


def _store_forecast_points(
    points: list[ForecastGenerationPoint],
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    horizon_min_hours: float | None = None,
    horizon_max_hours: float | None = None,
) -> int:
    valid_forecast_rows: list[dict[str, datetime | float]] = []
    for point in points:
        if start_time is not None and point.target_time < start_time:
            continue
        if end_time is not None and point.target_time > end_time:
            continue

        forecast_horizon_hours = (point.target_time - point.created_at).total_seconds() / 3600
        if horizon_min_hours is not None and forecast_horizon_hours < horizon_min_hours:
            continue
        if horizon_max_hours is not None and forecast_horizon_hours > horizon_max_hours:
            continue

        valid_forecast_rows.append(
            {
                "target_time": point.target_time,
                "created_at": point.created_at,
                "generation_mw": point.generation_mw,
            }
        )

    with SessionLocal.begin() as session:
        if valid_forecast_rows:
            forecast_stmt = insert(ForecastGeneration).values(valid_forecast_rows)
            session.execute(
                forecast_stmt.on_conflict_do_update(
                    index_elements=[ForecastGeneration.target_time, ForecastGeneration.created_at],
                    set_={"generation_mw": forecast_stmt.excluded.generation_mw},
                )
            )

    return len(valid_forecast_rows)


def _parse_actual_points(rows: list[dict[str, object]]) -> list[ActualGenerationPoint]:
    points: list[ActualGenerationPoint] = []
    for row in rows:
        try:
            points.append(ActualGenerationPoint.model_validate(row))
        except Exception:
            continue
    return points


def _parse_forecast_points(rows: list[dict[str, object]]) -> list[ForecastGenerationPoint]:
    points: list[ForecastGenerationPoint] = []
    for row in rows:
        try:
            points.append(ForecastGenerationPoint.model_validate(row))
        except Exception:
            continue
    return points


def _fetch_bmrs_rows(
    base_url: str, query_params: dict[str, str | list[str]]
) -> list[dict[str, object]]:
    url = base_url
    if query_params:
        url = f"{url}?{urlencode(query_params, doseq=True)}"

    request = UrlRequest(url=url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"BMRS request failed with status code {exc.code}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach BMRS API",
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="BMRS response is not valid JSON",
        ) from exc

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [row for row in payload["data"] if isinstance(row, dict)]

    return []


def _count_total_records() -> int:
    with SessionLocal() as session:
        actual_count = session.scalar(select(func.count(ActualGeneration.id))) or 0
        forecast_count = session.scalar(select(func.count(ForecastGeneration.id))) or 0
    return int(actual_count) + int(forecast_count)


def _reset_tables() -> None:
    with SessionLocal.begin() as session:
        session.execute(delete(ForecastGeneration))
        session.execute(delete(ActualGeneration))


def _load_series_data_from_db(
    start_time: datetime, end_time: datetime
) -> tuple[dict[datetime, float], dict[datetime, list[tuple[datetime, float]]]]:
    with SessionLocal() as session:
        actual_rows = session.execute(
            select(ActualGeneration.target_time, ActualGeneration.generation_mw).where(
                ActualGeneration.target_time >= start_time,
                ActualGeneration.target_time <= end_time,
            )
        ).all()

        forecast_rows = session.execute(
            select(
                ForecastGeneration.target_time,
                ForecastGeneration.created_at,
                ForecastGeneration.generation_mw,
            )
            .where(
                ForecastGeneration.target_time >= start_time,
                ForecastGeneration.target_time <= end_time,
            )
            .order_by(ForecastGeneration.target_time, ForecastGeneration.created_at.desc())
        ).all()

    actual_by_target = {row.target_time: row.generation_mw for row in actual_rows}
    forecasts_by_target: dict[datetime, list[tuple[datetime, float]]] = {}
    for row in forecast_rows:
        forecasts_by_target.setdefault(row.target_time, []).append((row.created_at, row.generation_mw))

    return actual_by_target, forecasts_by_target
