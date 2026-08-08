"""schemas/auth.py — the pydantic gate in front of every auth endpoint.

Fast, pure, and the first thing a hostile request meets. Covered here rather
than only through HTTP so a failure names the rule that broke rather than
"expected 422".
"""

import pytest
from pydantic import ValidationError

from backend.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    UserPublic,
)

VALID = {
    "username": "alice",
    "email": "alice@example.com",
    "password": "Password123",
    "confirm_password": "Password123",
}


def _register(**overrides) -> RegisterRequest:
    return RegisterRequest(**{**VALID, **overrides})


# --------------------------------------------------------------------------- #
# Password policy — shared by registration and both reset paths
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "password,reason",
    [
        ("Short1A", "7 chars, one under the minimum"),
        ("alllowercase1", "no uppercase letter"),
        ("NoDigitsHere", "no digit"),
        ("A1" + "a" * 29, "31 chars, one over the maximum"),
        ("", "empty"),
    ],
)
def test_passwords_failing_the_policy_are_rejected(password, reason):
    with pytest.raises(ValidationError):
        _register(password=password, confirm_password=password)


@pytest.mark.parametrize("password", ["Passwo1d", "A" * 29 + "1"])
def test_passwords_at_the_length_boundaries_are_accepted(password):
    """8 and 30 characters exactly — the bounds are inclusive."""
    assert len(password) in (8, 30)
    _register(password=password, confirm_password=password)


def test_the_policy_requires_no_lowercase_and_no_symbol():
    """Documents the actual rule rather than the one people assume: uppercase
    and digit only. "AAAAAAA1" is a legal password today."""
    _register(password="AAAAAAA1", confirm_password="AAAAAAA1")


def test_mismatched_confirmation_is_rejected():
    with pytest.raises(ValidationError, match="Passwords do not match"):
        _register(confirm_password="Password124")


# --------------------------------------------------------------------------- #
# Username
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "username",
    ["ab", "has spaces", "bad!char", "email@sign", "", "hy-phen", "dot.dot"],
)
def test_usernames_outside_the_allowed_pattern_are_rejected(username):
    with pytest.raises(ValidationError):
        _register(username=username)


@pytest.mark.parametrize("username", ["abc", "with_underscore", "MiXeD123"])
def test_usernames_matching_the_pattern_are_accepted(username):
    assert _register(username=username).username == username


def test_the_username_schema_imposes_no_maximum_length():
    """CURRENT BEHAVIOUR, and a real gap: the column is String(100), so a longer
    username reaches Postgres and fails as a 500 rather than a 422. Pinned so
    the day a max_length is added, this test is the reminder to flip it."""
    long_name = "a" * 200
    assert _register(username=long_name).username == long_name


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("email", ["not-an-email", "no@tld", "@example.com", "a b@example.com", ""])
def test_malformed_emails_are_rejected(email):
    with pytest.raises(ValidationError):
        _register(email=email)


# --------------------------------------------------------------------------- #
# Whitespace stripping — deliberately inconsistent across schemas
# --------------------------------------------------------------------------- #

def test_registration_strips_surrounding_whitespace():
    assert _register(username="  alice  ").username == "alice"


def test_login_strips_surrounding_whitespace():
    assert LoginRequest(email="alice@example.com", password="  hunter2  ").password == "hunter2"


def test_login_accepts_any_password_string_without_applying_the_policy():
    """Correct: the policy gates what you may *set*, not what you may submit.
    Applying it here would tell an attacker which guesses are even well-formed,
    and would lock out anyone whose password predates a policy change."""
    LoginRequest(email="alice@example.com", password="x")


# --------------------------------------------------------------------------- #
# Response shapes — the enumeration-resistant one in particular
# --------------------------------------------------------------------------- #

def test_the_register_response_carries_a_message_and_nothing_else():
    """Message-only ON PURPOSE. Any field that differed between "account
    created" and "email already taken" — a user_id, a verified flag — would
    re-open email enumeration on the endpoint."""
    assert set(RegisterResponse.model_fields) == {"message"}


def test_userpublic_exposes_only_the_four_fields_the_spa_needs():
    assert set(UserPublic.model_fields) == {"id", "username", "email", "verified"}


def test_reset_password_applies_the_same_strength_policy_as_registration():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(current_password="whatever", new_password="weak")
