"""core/security.py — token minting and JWT verification.

Every session decision in the app funnels through `verify_access_token`, and it
is pure, so this is the cheapest high-value coverage in the suite.

Settings are read at call time inside these functions, so monkeypatching
`backend.core.security.settings` works — unlike the rate-limit values, which are
frozen into decorators at import.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.core import security
from backend.core.config import settings
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    generate_verification_token,
    hash_token,
    verify_access_token,
    verify_refresh_token,
)

USER_ID = "6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d"


def _encode(payload: dict, *, secret: str | None = None, algorithm: str | None = None) -> str:
    return jwt.encode(
        payload,
        secret if secret is not None else settings.JWT_SECRET,
        algorithm=algorithm or settings.JWT_ALGORITHM,
    )


# --------------------------------------------------------------------------- #
# hash_token
# --------------------------------------------------------------------------- #

def test_hash_token_is_deterministic_and_is_a_sha256_hex_digest():
    digest = hash_token("some-token")
    assert digest == hash_token("some-token")
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_hash_token_separates_values_that_differ_by_one_character():
    assert hash_token("token-a") != hash_token("token-b")


# --------------------------------------------------------------------------- #
# Opaque token generation
# --------------------------------------------------------------------------- #

def test_verification_token_returns_a_raw_value_paired_with_its_own_digest():
    """The invariant, not the value: the raw token goes in the email and only
    the digest is persisted, so the pairing is what makes verification work."""
    raw, digest = generate_verification_token()
    assert hash_token(raw) == digest
    assert raw != digest


def test_generated_tokens_are_unique_across_calls():
    tokens = {generate_verification_token()[0] for _ in range(50)}
    assert len(tokens) == 50


def test_refresh_token_pairs_the_raw_value_with_its_digest_too():
    raw, digest = create_refresh_token(USER_ID)
    assert hash_token(raw) == digest


def test_refresh_tokens_are_not_bound_to_the_user_id_they_are_passed():
    """Documents current behaviour: create_refresh_token accepts a user_id and
    ignores it — the binding is the refresh_tokens row, not the token itself.
    If that ever changes, this test should be the one that fails."""
    raw_a, _ = create_refresh_token("user-a")
    raw_b, _ = create_refresh_token("user-b")
    assert raw_a != raw_b  # random, not derived
    assert verify_refresh_token(raw_a, hash_token(raw_a))


def test_verify_refresh_token_compares_a_raw_token_against_a_digest():
    raw, digest = create_refresh_token(USER_ID)
    assert verify_refresh_token(raw, digest) is True
    assert verify_refresh_token("something-else", digest) is False


# --------------------------------------------------------------------------- #
# Access tokens — the happy path
# --------------------------------------------------------------------------- #

def test_a_freshly_minted_access_token_round_trips_to_its_subject():
    assert verify_access_token(create_access_token(USER_ID)) == USER_ID


def test_access_tokens_carry_an_expiry_derived_from_the_configured_timeout(monkeypatch):
    monkeypatch.setattr(security.settings, "TIMEOUT_MINUTES", 30)
    before = datetime.now(timezone.utc)
    claims = jwt.decode(
        create_access_token(USER_ID),
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    expiry = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    assert timedelta(minutes=29) < expiry - before < timedelta(minutes=31)


# --------------------------------------------------------------------------- #
# Access tokens — every rejection returns None rather than raising
# --------------------------------------------------------------------------- #

def test_an_expired_token_is_rejected():
    expired = _encode({"sub": USER_ID, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)})
    assert verify_access_token(expired) is None


def test_a_token_with_no_exp_claim_is_rejected():
    """options={"require": [...]} is what makes this fail — without it a token
    with no expiry would verify forever."""
    assert verify_access_token(_encode({"sub": USER_ID})) is None


def test_a_token_with_no_sub_claim_is_rejected():
    assert verify_access_token(
        _encode({"exp": datetime.now(timezone.utc) + timedelta(minutes=5)})
    ) is None


def test_a_token_signed_with_a_different_secret_is_rejected():
    forged = _encode(
        {"sub": USER_ID, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        secret="a-completely-different-secret-value-here",
    )
    assert verify_access_token(forged) is None


# The warning is about the length of *this test's* signing key relative to
# SHA-512, not about anything the app does — the app only ever uses HS256.
@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_a_token_signed_with_a_different_algorithm_is_rejected(monkeypatch):
    token = _encode(
        {"sub": USER_ID, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        algorithm="HS512",
    )
    monkeypatch.setattr(security.settings, "JWT_ALGORITHM", "HS256")
    assert verify_access_token(token) is None


def test_an_unsigned_alg_none_token_is_rejected():
    """The classic JWT bypass: strip the signature and claim alg=none."""
    unsigned = jwt.encode(
        {"sub": USER_ID, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        key="",
        algorithm="none",
    )
    assert verify_access_token(unsigned) is None


@pytest.mark.parametrize(
    "token",
    ["", "garbage", "a.b.c", "Bearer sometoken", "..", "eyJhbGciOiJIUzI1NiJ9.e30."],
    ids=["empty", "garbage", "three-empty-segments", "header-prefix", "dots", "empty-claims"],
)
def test_malformed_tokens_are_rejected_without_raising(token):
    assert verify_access_token(token) is None


def test_a_tampered_payload_is_rejected():
    valid = create_access_token(USER_ID)
    header, payload, signature = valid.split(".")
    tampered = f"{header}.{payload[:-2]}XX.{signature}"
    assert verify_access_token(tampered) is None
