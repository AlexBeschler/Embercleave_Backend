from fastapi.testclient import TestClient

from app.auth import get_current_user_claims
from app.main import app


def test_bootstrap_requires_auth():
    client = TestClient(app)
    response = client.post("/users/bootstrap")
    assert response.status_code == 401


def test_bootstrap_rejects_invalid_token():
    client = TestClient(app)
    response = client.post(
        "/users/bootstrap", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_bootstrap_http_end_to_end(db, test_uid):
    app.dependency_overrides[get_current_user_claims] = lambda: {
        "uid": test_uid,
        "email": "test@example.com",
    }
    client = TestClient(app)
    try:
        response = client.post("/users/bootstrap")
        assert response.status_code == 200
        body = response.json()
        assert body["uid"] == test_uid
        assert body["email"] == "test@example.com"
        assert body["connectionStatus"] == "not_connected"
        assert body["activePeriodId"]

        second = client.post("/users/bootstrap")
        assert second.json()["activePeriodId"] == body["activePeriodId"]
    finally:
        app.dependency_overrides.clear()
        user_ref = db.collection("users").document(test_uid)
        for period in user_ref.collection("periods").stream():
            period.reference.delete()
        user_ref.delete()
