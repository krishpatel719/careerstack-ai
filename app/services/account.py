"""Self-service account deletion and cleanup of user-owned data."""

from app.services import auth as auth_service
from app.services.analyze import ANALYSES_COLLECTION
from app.services.discovery import COLLECTION as DISCOVERY_RUNS_COLLECTION
from app.services.extraction.parse_cache import COLLECTION as PARSED_RESUMES_COLLECTION
from app.store import delete_json, list_records, load_by_field

DELETE_SUCCESS_MESSAGE = (
    "Account deleted successfully. Associated analyses, discovery runs, "
    "and unused resume cache entries have also been removed."
)


def _delete_owned_records(
    collection: str,
    id_field: str,
    owner_field: str,
    user_id: str,
) -> int:
    """Delete records whose owner field exactly matches this user."""
    deleted = 0
    for record in list_records(collection):
        if record.get(owner_field) != user_id:
            continue
        record_id = record.get(id_field)
        if not isinstance(record_id, str) or not record_id:
            # Application-created records always have their public ID. Skipping
            # malformed legacy data is safer than guessing a deletion key.
            continue
        deleted += int(delete_json(collection, record_id))
    return deleted


def delete_account(user_id: str) -> dict:
    """Delete an account and all data owned exclusively by that account.

    The service is idempotent: a user that is already absent is treated as a
    completed deletion. Parsed resumes are shared by content hash, so a cache
    entry is removed only after the user's analyses are gone and no analysis
    left in the collection still references its ``resume_file_key``.
    """
    user_record = load_by_field(auth_service.COLLECTION, "user_id", user_id)
    if user_record is None:
        return {
            "message": DELETE_SUCCESS_MESSAGE,
            "deleted": {"analyses": 0, "discovery_runs": 0, "parsed_resumes": 0},
        }

    analyses = list_records(ANALYSES_COLLECTION)
    candidate_resume_keys = {
        record["resume_file_key"]
        for record in analyses
        if record.get("user_id") == user_id
        and isinstance(record.get("resume_file_key"), str)
        and record["resume_file_key"]
    }

    deleted_discovery_runs = _delete_owned_records(
        DISCOVERY_RUNS_COLLECTION, "run_id", "user_id", user_id
    )
    deleted_analyses = _delete_owned_records(
        ANALYSES_COLLECTION, "analysis_id", "user_id", user_id
    )

    remaining_resume_keys = {
        record["resume_file_key"]
        for record in list_records(ANALYSES_COLLECTION)
        if isinstance(record.get("resume_file_key"), str) and record["resume_file_key"]
    }
    deleted_resumes = sum(
        int(delete_json(PARSED_RESUMES_COLLECTION, key))
        for key in sorted(candidate_resume_keys - remaining_resume_keys)
    )

    # Delete the identity last. If cleanup fails, the account remains available
    # for a safe retry, and its existing token still resolves to it.
    user_key = auth_service._email_key(str(user_record["email"]))
    delete_json(auth_service.COLLECTION, user_key)

    return {
        "message": DELETE_SUCCESS_MESSAGE,
        "deleted": {
            "analyses": deleted_analyses,
            "discovery_runs": deleted_discovery_runs,
            "parsed_resumes": deleted_resumes,
        },
    }
