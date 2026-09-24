"""Resume-free opportunity search routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user
from app.models.user import UserPublic
from app.services.opportunities import DEFAULT_LIMIT, MAX_LIMIT, search_opportunities

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("")
async def search(
    role: str = Query(..., min_length=2, max_length=120),
    location: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_user: UserPublic = Depends(get_current_user),
) -> dict:
    """Return approved-source opportunities for a role and location.

    Authentication is required so this endpoint cannot be used as an open
    proxy for provider quota. Resume-specific matching remains in the
    analysis-backed discovery endpoint.
    """
    try:
        return await search_opportunities(role, location, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
