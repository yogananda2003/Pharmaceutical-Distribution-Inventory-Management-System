"""Unit tests for security primitives — no DB, no network."""
import time
import uuid

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)

# sync tests — no asyncio mark needed


# ── password ──────────────────────────────────────────────────────────────────


def test_hash_and_verify_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_is_bcrypt_prefix():
    hashed = hash_password("any")
    assert hashed.startswith("$2b$")


def test_different_hashes_for_same_input():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


# ── token hashing ─────────────────────────────────────────────────────────────


def test_hash_token_deterministic():
    assert hash_token("abc") == hash_token("abc")


def test_hash_token_length():
    assert len(hash_token("x")) == 64  # SHA-256 hex digest


def test_hash_token_different_inputs():
    assert hash_token("a") != hash_token("b")


# ── JWT access token ──────────────────────────────────────────────────────────


def test_create_and_decode_access_token():
    uid = uuid.uuid4()
    token = create_access_token(uid, "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_access_token_wrong_type_rejected():
    uid = uuid.uuid4()
    _, _ = create_refresh_token(uid)
    raw, _ = create_refresh_token(uid)
    with pytest.raises(ValueError):
        decode_access_token(raw)


def test_access_token_tampered_rejected():
    uid = uuid.uuid4()
    token = create_access_token(uid, "admin")
    tampered = token[:-4] + "xxxx"
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_access_token_invalid_string_rejected():
    with pytest.raises(ValueError):
        decode_access_token("not.a.jwt")


# ── JWT refresh token ─────────────────────────────────────────────────────────


def test_create_and_decode_refresh_token():
    uid = uuid.uuid4()
    raw, expires_at = create_refresh_token(uid)
    payload = decode_refresh_token(raw)
    assert payload["sub"] == str(uid)
    assert payload["type"] == "refresh"
    assert expires_at is not None


def test_refresh_token_wrong_type_rejected():
    uid = uuid.uuid4()
    access = create_access_token(uid, "customer")
    with pytest.raises(ValueError):
        decode_refresh_token(access)


def test_refresh_token_expiry_in_future():
    uid = uuid.uuid4()
    _, expires_at = create_refresh_token(uid)
    assert expires_at.timestamp() > time.time()
