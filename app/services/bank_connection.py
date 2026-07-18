from google.cloud import firestore

from app.plaid_client import create_link_token, exchange_public_token, remove_item
from app.services.plaid_sync import sync_user_transactions


def create_link_token_for_user(uid: str, webhook_url: str) -> str:
    return create_link_token(uid, webhook_url)


def connect_bank(db: firestore.Client, uid: str, public_token: str) -> dict:
    """architecture.md §3.2: exchange public_token, record the Item, run the
    initial transaction sync. If the initial sync raises after the Item is
    recorded, connectionStatus is left "connected" (the Item itself was
    created successfully) and the error propagates so the app can prompt a
    retry — the connection is never rolled back over a transient sync
    failure.
    """
    access_token, item_id = exchange_public_token(public_token)

    user_ref = db.collection("users").document(uid)
    user_ref.update(
        {
            "plaidAccessToken": access_token,
            "plaidItemId": item_id,
            "connectionStatus": "connected",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    db.collection("enrollments").document(item_id).set({"uid": uid})

    sync_user_transactions(db, uid, refresh_all_account_balances=False)

    return {"connectionStatus": "connected"}


def disconnect_bank(db: firestore.Client, uid: str) -> dict:
    """architecture.md §3.4: unlink-only — budgets/transactions/accounts/
    periods are left untouched. /item/remove happens before the Firestore
    cleanup so a failure there is surfaced rather than silently orphaning a
    live Item.
    """
    user_ref = db.collection("users").document(uid)
    user_data = user_ref.get().to_dict() or {}
    access_token = user_data.get("plaidAccessToken")
    item_id = user_data.get("plaidItemId")

    if access_token:
        remove_item(access_token)

    user_ref.update(
        {
            "plaidAccessToken": None,
            "plaidItemId": None,
            "connectionStatus": "disconnected",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    if item_id:
        db.collection("enrollments").document(item_id).delete()

    return {"connectionStatus": "disconnected"}
