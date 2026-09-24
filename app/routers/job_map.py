"""Public, provider-free endpoints for the persisted job map."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services.job_map import (
    DEFAULT_MAP_LIMIT,
    MAX_MAP_LIMIT,
    JobMapUnavailableError,
    get_map_job,
    search_map,
)

router = APIRouter(prefix="/api/job-map", tags=["job-map"])


@router.get("")
async def job_map(
    role: str | None = Query(None, min_length=2, max_length=120),
    location: str | None = Query(None, min_length=2, max_length=120),
    company: str | None = Query(None, min_length=2, max_length=120),
    source: Literal["jsearch", "greenhouse", "lever", "ashby", "adzuna"] | None = None,
    remote: bool | None = None,
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, ge=1, le=1000),
    limit: int = Query(DEFAULT_MAP_LIMIT, ge=1, le=MAX_MAP_LIMIT),
) -> dict:
    """Read current, geocoded jobs from MongoDB without calling providers."""
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Latitude and longitude must be supplied together.",
        )
    try:
        return search_map(
            role=role,
            location=location,
            company=company,
            source=source,
            remote=remote,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )
    except JobMapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{job_id}")
async def job_map_detail(job_id: str) -> dict:
    """One client-safe job-map record with a sanitized external link."""
    try:
        job = get_map_job(job_id)
    except JobMapUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="No mapped job found with that ID.")
    return job
