from fastapi import APIRouter, Depends
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.firestore_client import get_firestore_client
from app.services.plaid_sync import sync_user_transactions

router = APIRouter(tags=["internal"])


@router.post("/reconcile")
def reconcile(db: firestore.Client = Depends(get_firestore_client)) -> dict:
    """architecture.md §3.3.2. Daily safety-net sync, invoked by Cloud
    Scheduler against the IAM-restricted embercleave-internal service (see
    the SERVICE_ROLE gate in app/main.py / iac/cloud_run.tf). Runs the same
    shared sync engine as the webhook handler for every connected user.
    Isolates per-user failures so one broken Item doesn't block the safety
    net for everyone else.
    """
    synced = 0
    failed = []
    query = db.collection("users").where(filter=FieldFilter("connectionStatus", "==", "connected"))
    for snapshot in query.stream():
        uid = snapshot.id
        try:
            sync_user_transactions(db, uid, refresh_all_account_balances=True)
            synced += 1
        except Exception:
            failed.append(uid)
    return {"synced": synced, "failed": failed}
