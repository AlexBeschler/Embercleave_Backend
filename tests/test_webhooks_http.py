import base64
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from plaid.model.jwk_public_key import JWKPublicKey

from app.main import app


def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _keypair(kid="test-kid"):
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
        expired_at=None,
    )
    return private_key, jwk


def _signed_request(private_key, kid, body: bytes) -> str:
    claims = {"iat": int(time.time()), "request_body_sha256": hashlib.sha256(body).hexdigest()}
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": kid})


def _empty_page():
    return SimpleNamespace(accounts=[], added=[], modified=[], removed=[], has_more=False, next_cursor="c-1")


def test_webhook_requires_verification_header():
    client = TestClient(app)
    response = client.post("/webhooks/plaid", content=b"{}")
    assert response.status_code == 401


def test_webhook_rejects_invalid_signature():
    client = TestClient(app)
    response = client.post(
        "/webhooks/plaid", content=b"{}", headers={"Plaid-Verification": "not-a-real-jwt"}
    )
    assert response.status_code == 401


def test_webhook_unknown_item_is_acknowledged_without_error():
    private_key, jwk = _keypair()
    body = b'{"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": "no-such-item"}'
    token = _signed_request(private_key, jwk.kid, body)

    with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
        client = TestClient(app)
        response = client.post(
            "/webhooks/plaid", content=body, headers={"Plaid-Verification": token, "Content-Type": "application/json"}
        )
    assert response.status_code == 200
    assert response.json() == {"acknowledged": True}


def test_webhook_transactions_triggers_sync(db, test_uid):
    db.collection("users").document(test_uid).set(
        {
            "connectionStatus": "connected",
            "plaidAccessToken": "access-tok",
            "plaidItemId": "item-webhook-1",
            "plaidCursor": None,
            "activePeriodId": "period-1",
        }
    )
    db.collection("enrollments").document("item-webhook-1").set({"uid": test_uid})
    try:
        private_key, jwk = _keypair()
        body = (
            b'{"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", '
            b'"item_id": "item-webhook-1"}'
        )
        token = _signed_request(private_key, jwk.kid, body)

        with (
            patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk),
            patch("app.services.plaid_sync.sync_transactions_page", return_value=_empty_page()),
            patch("app.services.plaid_sync.get_accounts", return_value=[]) as mock_get_accounts,
        ):
            client = TestClient(app)
            response = client.post(
                "/webhooks/plaid",
                content=body,
                headers={"Plaid-Verification": token, "Content-Type": "application/json"},
            )
        assert response.status_code == 200
        mock_get_accounts.assert_called_once_with("access-tok")

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["plaidCursor"] == "c-1"
    finally:
        db.collection("enrollments").document("item-webhook-1").delete()
        db.collection("users").document(test_uid).delete()


def test_webhook_item_error_sets_needs_attention(db, test_uid):
    db.collection("users").document(test_uid).set(
        {
            "connectionStatus": "connected",
            "plaidAccessToken": "access-tok",
            "plaidItemId": "item-webhook-2",
            "plaidCursor": None,
            "activePeriodId": "period-1",
        }
    )
    db.collection("enrollments").document("item-webhook-2").set({"uid": test_uid})
    try:
        private_key, jwk = _keypair()
        body = b'{"webhook_type": "ITEM", "webhook_code": "ERROR", "item_id": "item-webhook-2"}'
        token = _signed_request(private_key, jwk.kid, body)

        with patch("app.plaid_webhook_verify.get_webhook_verification_key", return_value=jwk):
            client = TestClient(app)
            response = client.post(
                "/webhooks/plaid",
                content=body,
                headers={"Plaid-Verification": token, "Content-Type": "application/json"},
            )
        assert response.status_code == 200

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["connectionStatus"] == "needs_attention"
    finally:
        db.collection("enrollments").document("item-webhook-2").delete()
        db.collection("users").document(test_uid).delete()
