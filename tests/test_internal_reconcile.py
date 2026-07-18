from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import internal


def _client():
    test_app = FastAPI()
    test_app.include_router(internal.router)
    return TestClient(test_app)


def test_reconcile_syncs_only_connected_users(db, test_uid):
    other_uid = f"{test_uid}-other"
    db.collection("users").document(test_uid).set({"connectionStatus": "connected", "activePeriodId": "p1"})
    db.collection("users").document(other_uid).set({"connectionStatus": "not_connected", "activePeriodId": "p1"})
    try:
        with patch("app.routers.internal.sync_user_transactions") as mock_sync:
            response = _client().post("/reconcile")
        assert response.status_code == 200
        synced_uids = {call.args[1] for call in mock_sync.call_args_list}
        assert test_uid in synced_uids
        assert other_uid not in synced_uids
    finally:
        db.collection("users").document(test_uid).delete()
        db.collection("users").document(other_uid).delete()


def test_reconcile_isolates_per_user_failures(db, test_uid):
    other_uid = f"{test_uid}-other"
    db.collection("users").document(test_uid).set({"connectionStatus": "connected", "activePeriodId": "p1"})
    db.collection("users").document(other_uid).set({"connectionStatus": "connected", "activePeriodId": "p1"})

    def _side_effect(db_arg, uid, refresh_all_account_balances):
        if uid == test_uid:
            raise RuntimeError("boom")

    try:
        with patch("app.routers.internal.sync_user_transactions", side_effect=_side_effect) as mock_sync:
            response = _client().post("/reconcile")
        assert response.status_code == 200
        body = response.json()
        assert test_uid in body["failed"]
        assert other_uid not in body["failed"]
        synced_uids = {call.args[1] for call in mock_sync.call_args_list}
        assert {test_uid, other_uid} <= synced_uids
    finally:
        db.collection("users").document(test_uid).delete()
        db.collection("users").document(other_uid).delete()
