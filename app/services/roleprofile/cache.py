"""Disk cache for mined role profiles.

Adzuna's free tier is ~1000 calls/month; a mining run costs 3 calls (one
per query variant), so re-mining on every request would burn through it
fast. Cached profiles live under data/role_profiles/ via app/store.py.
"""

import hashlib
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.roleprofile.miner import (
    RoleProfileDataUnavailableError,
    is_usable_role_profile,
    mine_role_profile,
    require_usable_role_profile,
)
from app.store import list_records, load_json, save_json

COLLECTION = "role_profiles"
CACHE_TTL_DAYS = 7

# A city-level location can turn up too few postings to mine anything
# meaningful. Below this, get_or_mine retries with LOCATION_FALLBACK_TARGET
# (half of miner.py's default target_postings=40) instead of returning a
# profile with too little data behind it.
LOCATION_FALLBACK_MIN_POSTINGS = 20
LOCATION_FALLBACK_TARGET = "India"


def _cache_key(role: str, location: str) -> str:
    raw = f"{role.lower()}|{location.lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _is_fresh(profile: dict) -> bool:
    sampled_at = profile.get("sampled_at")
    if not sampled_at:
        return False

    try:
        sampled_time = datetime.fromisoformat(sampled_at)
    except ValueError:
        return False

    if sampled_time.tzinfo is None:
        sampled_time = sampled_time.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - sampled_time < timedelta(days=CACHE_TTL_DAYS)


def _matches_request(profile: dict, role: str, location: str) -> bool:
    return (
        str(profile.get("role", "")).strip().lower() == role.strip().lower()
        and str(profile.get("location", "")).strip().lower() == location.strip().lower()
    )


async def _get_cached_or_mine(role: str, location: str) -> dict:
    """Cached role profile for one exact (role, location) pair; mines a
    fresh one only when the cache is missing or older than CACHE_TTL_DAYS.

    In DEMO_MODE, this never touches the network: it returns the cached
    profile if one exists, or raises RuntimeError if it doesn't. That's
    what lets the demo run with zero live network dependency -- cache the
    profiles you need beforehand, with DEMO_MODE off.
    """
    key = _cache_key(role, location)
    cached = load_json(COLLECTION, key)
    cache_matches_request = bool(cached and _matches_request(cached, role, location))

    if settings.demo_mode:
        if cache_matches_request and is_usable_role_profile(cached):
            return cached
        if cached is not None and not cache_matches_request:
            raise RoleProfileDataUnavailableError(
                f"DEMO_MODE found a cached profile for a different role or "
                f"location than role={role!r}, location={location!r}."
            )
        raise RoleProfileDataUnavailableError(
            f"DEMO_MODE is on and no cached role profile exists for "
            f"role={role!r}, location={location!r}. Mine and cache it with "
            f"DEMO_MODE off before relying on it in demo mode."
        )

    if cache_matches_request and _is_fresh(cached) and is_usable_role_profile(cached):
        return cached

    profile = await mine_role_profile(role, location)
    # Mining owns the source-of-truth validation, but keep the boundary
    # defensive: malformed/empty results must never become a normal fresh
    # cache entry, even if a caller or a future miner change regresses.
    require_usable_role_profile(profile)
    if not _matches_request(profile, role, location):
        raise RoleProfileDataUnavailableError(
            f"Mined profile identity did not match role={role!r}, location={location!r}."
        )
    save_json(COLLECTION, key, profile)
    return profile


async def get_or_mine(role: str, location: str) -> dict:
    """Cached role profile for (role, location), with an India fallback.

    A sparse *usable* requested-location profile (fewer than
    LOCATION_FALLBACK_MIN_POSTINGS postings) falls back to usable market data
    for the same role in India when available. The returned result is
    annotated so callers can distinguish that data from an exact-location
    result:

        {"requested_location": "Ahmedabad", "used_location": "India",
         "requested_postings_sampled": 17}

    A zero-result/unusable requested location also gets this same-role India
    fallback. If India is not usable, the domain-unavailable error remains
    visible; an empty profile is never returned as if it were fresh data.

    ``location_fallback`` is always present on the returned dict -- ``None``
    when no fallback happened. It is added here, not stored in the cached
    JSON, because it describes this lookup rather than the mined data.
    In DEMO_MODE the fallback lookup is also cache-only; if India is not
    cached, a usable sparse primary profile is returned unchanged.
    """
    is_fallback_target = location.strip().lower() == LOCATION_FALLBACK_TARGET.lower()

    try:
        profile = await _get_cached_or_mine(role, location)
    except RoleProfileDataUnavailableError:
        if is_fallback_target:
            raise
        # A zero-result city should still get the same-role India fallback,
        # just like a sparse city with usable data. If India is unavailable,
        # propagate the requested-profile error rather than returning empty.
        fallback_profile = await _get_cached_or_mine(role, LOCATION_FALLBACK_TARGET)
        return {
            **fallback_profile,
            "location_fallback": {
                "requested_location": location,
                "used_location": LOCATION_FALLBACK_TARGET,
                "requested_postings_sampled": 0,
            },
        }

    if not is_fallback_target and profile.get("postings_sampled", 0) < LOCATION_FALLBACK_MIN_POSTINGS:
        try:
            fallback_profile = await _get_cached_or_mine(role, LOCATION_FALLBACK_TARGET)
        except RuntimeError:
            # DEMO_MODE and India isn't cached: preserve the usable primary
            # profile. In live mode this also means there was no usable India
            # result, so the sparse primary remains the best exact-role data.
            pass
        else:
            return {
                **fallback_profile,
                "location_fallback": {
                    "requested_location": location,
                    "used_location": LOCATION_FALLBACK_TARGET,
                    "requested_postings_sampled": profile.get("postings_sampled", 0),
                },
            }

    return {**profile, "location_fallback": None}


def get_most_recent_cached_profile() -> dict | None:
    """The freshest cached role profile across every role/location ever
    mined, or None if nothing has ever been cached.

    Last-resort fallback for when get_or_mine can't produce a profile for
    the specifically-requested role/location at all -- see
    app/services/analyze.py's degraded-analysis handling. Not used by
    get_or_mine itself; get_or_mine's job is one exact (role, location),
    this is "give me anything at all".
    """
    profiles = [profile for profile in list_records(COLLECTION) if is_usable_role_profile(profile)]
    if not profiles:
        return None

    # ISO 8601 strings with a consistent format sort chronologically as
    # plain strings -- no need to parse them into datetimes just to
    # compare.
    return max(profiles, key=lambda profile: profile.get("sampled_at") or "")
