from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.cloud import firestore

from app.firestore_client import get_firestore_client
from app.plaid_webhook_verify import verify_webhook
from app.services.plaid_sync import sync_user_transactions

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ITEM_ERROR_CODES = {"ERROR", "USER_PERMISSION_REVOKED"}


@router.post("/plaid")
async def plaid_webhook(
    request: Request,
    db: firestore.Client = Depends(get_firestore_client),
) -> dict:
    """architecture.md §3.3.1. Unauthenticated at the network level, signature-
    verified in code (see plaid_webhook_verify.verify_webhook) — an invalid or
    unverifiable signature is rejected with 401 and nothing is read or
    written. Idempotent: safe for Plaid to redeliver."""
    token = request.headers.get("Plaid-Verification")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Plaid-Verification header")

    raw_body = await request.body()
    verify_webhook(token, raw_body)

    payload = await request.json()
    webhook_type = payload.get("webhook_type")
    webhook_code = payload.get("webhook_code")
    item_id = payload.get("item_id")

    enrollment = db.collection("enrollments").document(item_id).get() if item_id else None
    if not enrollment or not enrollment.exists:
        return {"acknowledged": True}
    uid = enrollment.to_dict()["uid"]

    if webhook_type == "TRANSACTIONS":
        sync_user_transactions(db, uid, refresh_all_account_balances=True)
    elif webhook_type == "ITEM" and webhook_code in _ITEM_ERROR_CODES:
        db.collection("users").document(uid).update(
            {"connectionStatus": "needs_attention", "updatedAt": firestore.SERVER_TIMESTAMP}
        )

    return {"acknowledged": True}
