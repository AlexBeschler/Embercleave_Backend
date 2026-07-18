import hashlib
import hmac
import time

import jwt
from fastapi import HTTPException, status

from app.plaid_client import get_webhook_verification_key

_MAX_IAT_AGE_SECONDS = 5 * 60


def verify_webhook(token: str, raw_body: bytes) -> dict:
    """Verifies a Plaid webhook's Plaid-Verification JWT per Plaid's
    documented webhook-verification algorithm (architecture.md §3.3.1/§5.4):
    ES256 signature against a key fetched from /webhook_verification_key/get
    (cached by kid), a fresh `iat` claim, and a `request_body_sha256` claim
    matching the actual raw body — all three must hold before any data is
    read or written. Raises 401 on any failure.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed webhook token") from exc

    if header.get("alg") != "ES256":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unexpected webhook token algorithm")

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook token missing kid")

    try:
        jwk = get_webhook_verification_key(kid)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to fetch webhook verification key"
        ) from exc

    if jwk.expired_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook verification key has expired")

    public_key = jwt.PyJWK(
        {"kty": jwk.kty, "crv": jwk.crv, "kid": jwk.kid, "x": jwk.x, "y": jwk.y},
        algorithm="ES256",
    ).key

    try:
        claims = jwt.decode(token, key=public_key, algorithms=["ES256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature") from exc

    iat = claims.get("iat")
    if iat is None or abs(time.time() - iat) > _MAX_IAT_AGE_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook token is stale")

    expected_hash = hashlib.sha256(raw_body).hexdigest()
    if not hmac.compare_digest(expected_hash, claims.get("request_body_sha256", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook body hash mismatch")

    return claims
