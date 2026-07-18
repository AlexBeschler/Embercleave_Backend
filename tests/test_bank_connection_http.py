from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import get_current_user_claims
from app.main import app


def _empty_page():
    return SimpleNamespace(accounts=[], added=[], modified=[], removed=[], has_more=False, next_cursor=None)


def _seed_user(db, uid, **overrides):
    data = {
        "email": "test@example.com",
        "connectionStatus": "not_connected",
        "plaidItemId": None,
        "plaidAccessToken": None,
        "plaidCursor": None,
        "activePeriodId": "period-1",
    }
    data.update(overrides)
    db.collection("users").document(uid).set(data)


def _cleanup(db, uid, item_id=None):
    user_ref = db.collection("users").document(uid)
    for sub in ("accounts", "transactions", "periods"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    user_ref.delete()
    if item_id:
        db.collection("enrollments").document(item_id).delete()


def test_link_token_requires_auth():
    client = TestClient(app)
    response = client.post("/bank-connection/link-token")
    assert response.status_code == 401


def test_link_token_returns_token_and_derives_webhook_from_request(test_uid):
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    try:
        with patch("app.services.bank_connection.create_link_token", return_value="link-token-xyz") as mock_create:
            client = TestClient(app, base_url="https://embercleave-api-dev.example.com")
            response = client.post("/bank-connection/link-token")
        assert response.status_code == 200
        assert response.json() == {"linkToken": "link-token-xyz"}
        mock_create.assert_called_once_with(test_uid, "https://embercleave-api-dev.example.com/webhooks/plaid")
    finally:
        app.dependency_overrides.clear()


def test_connect_bank_full_flow(db, test_uid):
    _seed_user(db, test_uid)
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    try:
        with (
            patch("app.services.bank_connection.exchange_public_token", return_value=("access-tok", "item-xyz")),
            patch("app.services.plaid_sync.sync_transactions_page", return_value=_empty_page()),
        ):
            client = TestClient(app)
            response = client.post("/bank-connection", json={"publicToken": "public-abc"})
        assert response.status_code == 200
        assert response.json() == {"connectionStatus": "connected"}

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["plaidAccessToken"] == "access-tok"
        assert user["plaidItemId"] == "item-xyz"
        assert user["connectionStatus"] == "connected"

        enrollment = db.collection("enrollments").document("item-xyz").get()
        assert enrollment.exists
        assert enrollment.to_dict()["uid"] == test_uid
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid, item_id="item-xyz")


def test_disconnect_bank_full_flow(db, test_uid):
    _seed_user(
        db,
        test_uid,
        connectionStatus="connected",
        plaidAccessToken="access-tok",
        plaidItemId="item-xyz",
    )
    db.collection("enrollments").document("item-xyz").set({"uid": test_uid})
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    try:
        with patch("app.services.bank_connection.remove_item") as mock_remove:
            client = TestClient(app)
            response = client.post("/bank-connection/disconnect")
        assert response.status_code == 200
        assert response.json() == {"connectionStatus": "disconnected"}
        mock_remove.assert_called_once_with("access-tok")

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["plaidAccessToken"] is None
        assert user["plaidItemId"] is None
        assert user["connectionStatus"] == "disconnected"

        assert not db.collection("enrollments").document("item-xyz").get().exists
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_disconnect_without_live_connection_skips_item_remove(db, test_uid):
    _seed_user(db, test_uid, connectionStatus="disconnected")
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    try:
        with patch("app.services.bank_connection.remove_item") as mock_remove:
            client = TestClient(app)
            response = client.post("/bank-connection/disconnect")
        assert response.status_code == 200
        mock_remove.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)
