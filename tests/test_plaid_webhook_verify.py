import base64
import hashlib
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from plaid.model.jwk_public_key import JWKPublicKey

from app.plaid_webhook_verify import verify_webhook


def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _make_keypair(kid="test-kid-1", expired_at=None):
    private_key = ec.generate_private_key(ec.SECP256R1())
    numbers = private_key.public_key().public_numbers()
    jwk = JWKPublicKey(
        alg="ES256",
        crv="P-256",
        kid=kid,
        kty="EC",
        use="sig",
        x=_b64url_uint(numbers.x),
        y=_b64url_uint(numbers.y),
        created_at=int(time.time()),
        expired_at=expired_at,
    )
    return private_key, jwk


def _sign(private_key, kid, claims):
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": kid})


def _claims_for(body: bytes, iat_offset_seconds: int = 0) -> dict:
    return {
        "iat": int(time.time()) + iat_offset_seconds,
        "request_body_sha256": hashlib.sha256(body).hexdigest(),
    }


def test_verify_webhook_accepts_valid_signature():
    private_key, jwk = _make_keypair()
    body = b'{"webhook_type": "TRANSACTIONS", "item_id": "item-1"}'
    token = _sign(private_key, jwk.kid, _claims_for(body))

    with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
        claims = verify_webhook(token, body)
    assert claims["request_body_sha256"] == hashlib.sha256(body).hexdigest()


def test_verify_webhook_rejects_tampered_body():
    private_key, jwk = _make_keypair()
    body = b'{"a": 1}'
    token = _sign(private_key, jwk.kid, _claims_for(body))

    with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook(token, b'{"a": 2}')
    assert exc_info.value.status_code == 401


def test_verify_webhook_rejects_signature_from_wrong_key():
    _, jwk = _make_keypair()
    other_private_key, _ = _make_keypair()
    body = b"{}"
    token = _sign(other_private_key, jwk.kid, _claims_for(body))

    with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_verify_webhook_rejects_stale_iat():
    private_key, jwk = _make_keypair()
    body = b"{}"
    token = _sign(private_key, jwk.kid, _claims_for(body, iat_offset_seconds=-3600))

    with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_verify_webhook_rejects_expired_key():
    private_key, jwk = _make_keypair(expired_at=int(time.time()) - 10)
    body = b"{}"
    token = _sign(private_key, jwk.kid, _claims_for(body))

    with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_verify_webhook_rejects_missing_kid_header():
    private_key, _ = _make_keypair()
    body = b"{}"
    token = jwt.encode(_claims_for(body), private_key, algorithm="ES256")  # no kid header

    with pytest.raises(HTTPException) as exc_info:
        verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_verify_webhook_rejects_malformed_token():
    with pytest.raises(HTTPException) as exc_info:
        verify_webhook("not-a-jwt", b"{}")
    assert exc_info.value.status_code == 401
