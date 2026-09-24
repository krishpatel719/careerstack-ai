"""Focused validation tests for runtime settings and registration input."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models.user import PASSWORD_MAX_BYTES, UserCreate


@pytest.mark.parametrize("jwt_secret", ["", " ", "\t\n"])
def test_settings_reject_blank_jwt_secret(jwt_secret):
    with pytest.raises(ValidationError):
        Settings(jwt_secret=jwt_secret)


@pytest.mark.parametrize(
    ("password", "is_valid"),
    [
        ("a" * PASSWORD_MAX_BYTES, True),
        ("é" * (PASSWORD_MAX_BYTES // 2), True),
        ("é" * (PASSWORD_MAX_BYTES // 2 + 1), False),
    ],
)
def test_user_create_validates_password_utf8_byte_length(password, is_valid):
    values = {"name": "Test User", "email": "user@example.com", "password": password}

    if is_valid:
        assert UserCreate(**values).password == password
    else:
        with pytest.raises(ValidationError):
            UserCreate(**values)
