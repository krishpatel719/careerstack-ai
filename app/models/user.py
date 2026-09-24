"""Pydantic schemas for authentication.

UserPublic never includes the password hash -- that's the entire reason it
exists as a model distinct from the stored user record.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# bcrypt hashes at most 72 bytes of the password and raises ValueError
# beyond that rather than silently truncating (a deliberate bcrypt 4.x+
# safety change -- silent truncation would let two different long
# passwords collide on the same hash). Capping it here turns an over-long
# password into an ordinary 422 validation error instead of an unhandled
# exception out of hash_password(). The limit is on encoded bytes, not
# Unicode characters, so multibyte passwords are validated accurately too.
PASSWORD_MAX_BYTES = 72


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_must_fit_bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class AccountDeleteRequest(BaseModel):
    """Explicit, machine-checkable confirmation for destructive account deletion."""

    confirm: Literal[True]


class AccountDeleteResponse(BaseModel):
    message: str
    deleted: dict[str, int]


class UserPublic(BaseModel):
    user_id: str
    email: str
    name: str
    created_at: str


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
