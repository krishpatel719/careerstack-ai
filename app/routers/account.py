"""Authenticated self-service account routes."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import AccountDeleteRequest, AccountDeleteResponse, UserPublic
from app.services import account as account_service

router = APIRouter(prefix="/api", tags=["account"])


@router.delete("/account", response_model=AccountDeleteResponse)
async def delete_account(
    payload: AccountDeleteRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> dict:
    return account_service.delete_account(current_user.user_id)
