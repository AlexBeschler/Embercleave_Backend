from concurrent.futures import ThreadPoolExecutor

from app.services.users import bootstrap_user


def _cleanup(db, uid):
    user_ref = db.collection("users").document(uid)
    for period in user_ref.collection("periods").stream():
        period.reference.delete()
    user_ref.delete()


def test_bootstrap_creates_user_and_active_period(db, test_uid):
    try:
        result = bootstrap_user(db, test_uid, email="test@example.com")

        assert result["connectionStatus"] == "not_connected"
        assert result["email"] == "test@example.com"
        assert result["activePeriodId"]

        user_snapshot = db.collection("users").document(test_uid).get()
        assert user_snapshot.exists
        user_data = user_snapshot.to_dict()
        assert user_data["activePeriodId"] == result["activePeriodId"]
        assert user_data["plaidItemId"] is None
        assert user_data["plaidAccessToken"] is None
        assert user_data["plaidCursor"] is None

        period_snapshot = (
            db.collection("users")
            .document(test_uid)
            .collection("periods")
            .document(result["activePeriodId"])
            .get()
        )
        assert period_snapshot.exists
        assert period_snapshot.to_dict()["status"] == "active"
        assert period_snapshot.to_dict()["clearedAt"] is None
    finally:
        _cleanup(db, test_uid)


def test_bootstrap_is_idempotent(db, test_uid):
    try:
        first = bootstrap_user(db, test_uid, email="test@example.com")
        second = bootstrap_user(db, test_uid, email="different@example.com")

        assert second["activePeriodId"] == first["activePeriodId"]
        # second call is a no-op: the email from the *first* call wins,
        # a later call never overwrites the existing user doc.
        assert second["email"] == "test@example.com"

        periods = list(
            db.collection("users").document(test_uid).collection("periods").stream()
        )
        assert len(periods) == 1
    finally:
        _cleanup(db, test_uid)


def test_bootstrap_concurrent_calls_create_only_one_period(db, test_uid):
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(bootstrap_user, db, test_uid, "test@example.com")
                for _ in range(2)
            ]
            results = [f.result() for f in futures]
        assert results[0]["activePeriodId"] == results[1]["activePeriodId"]

        periods = list(
            db.collection("users").document(test_uid).collection("periods").stream()
        )
        assert len(periods) == 1
    finally:
        _cleanup(db, test_uid)
