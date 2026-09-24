"""Authentication: password hashing, JWT issuance/verification, user
storage. All auth logic lives here -- routes only validate input, call
into this module, and shape the HTTP response.

bcrypt directly, not passlib: passlib 1.7.4 has a known incompatibility
with bcrypt 4.x that raises on import.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings
from app.models.user import UserPublic
from app.store import create_json_if_absent, load_by_field, load_json

COLLECTION = "users"

# A real bcrypt hash, computed once at import time, verified against on
# every login attempt for an email that doesn't exist -- so a failed
# login takes about as long whether or not the email is registered.
# Nothing authenticates against this; the "password" it was hashed from
# isn't a real credential.
_DUMMY_HASH = bcrypt.hashpw(b"timing-safety-dummy-password", bcrypt.gensalt()).decode("utf-8")


class TokenError(Exception):
    """Base class for decode_token failures."""


class ExpiredTokenError(TokenError):
    """The token was well-formed but its exp claim has passed."""


class InvalidTokenError(TokenError):
    """The token is malformed, has a bad signature, or is missing sub."""


def _email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # e.g. plain longer than bcrypt's 72-byte limit -- can never match
        # a hash that was itself capped at registration time (UserCreate's
        # own max_length), so this is just "wrong password", not an error.
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """Returns the user_id (the token's "sub" claim).

    Raises ExpiredTokenError or InvalidTokenError with a distinct message
    for each; the get_current_user dependency turns those into the right
    401 detail.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("Session expired, please log in again") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid credentials") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Invalid credentials")
    return user_id


def _to_public(record: dict) -> UserPublic:
    # Records saved before the name field existed have none. Falling back
    # to the email's local part means an old ./data/users record still
    # reads fine instead of 500ing on a missing key.
    name = record.get("name")
    if not name:
        email = record.get("email", "")
        name = email.split("@", 1)[0] if "@" in email else email
    return UserPublic(user_id=record["user_id"], email=record["email"], name=name, created_at=record["created_at"])


def create_user(email: str, password: str, name: str) -> UserPublic:
    """Raises ValueError if the email is already registered -- the route
    maps that to a 409, not a 500.
    """
    key = _email_key(email)
    record = {
        "user_id": uuid.uuid4().hex,
        "email": email.strip().lower(),
        "name": name.strip(),
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if not create_json_if_absent(COLLECTION, key, record):
        raise ValueError("An account with that email already exists.")

    return _to_public(record)


def authenticate(email: str, password: str) -> UserPublic | None:
    """None on any failure -- wrong email, wrong password, or no such
    account -- so the route can give the same generic "Incorrect email or
    password" for all three. Always runs a real bcrypt verify (against
    the account's own hash, or the dummy one), so response time doesn't
    reveal whether the email exists.
    """
    record = load_json(COLLECTION, _email_key(email))
    if record is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, record["password_hash"]):
        return None
    return _to_public(record)


def get_user_by_id(user_id: str) -> UserPublic | None:
    """Resolve a JWT subject through the indexed MongoDB user_id field."""
    record = load_by_field(COLLECTION, "user_id", user_id)
    return _to_public(record) if record else None
