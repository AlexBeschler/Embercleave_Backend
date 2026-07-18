from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.auth import get_current_uid
from app.errors import NotFoundError
from app.firestore_client import get_firestore_client
from app.models import AcceptTransactionRequest, TransactionResponse
from app.services.transactions import accept_transaction, list_transactions, reject_transaction, unreject_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionResponse])
def get_transactions(
    status: str | None = None,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> list[TransactionResponse]:
    return [TransactionResponse(**t) for t in list_transactions(db, uid, status=status)]


@router.post("/{transaction_id}/accept", response_model=TransactionResponse)
def accept(
    transaction_id: str,
    body: AcceptTransactionRequest,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> TransactionResponse:
    try:
        return TransactionResponse(**accept_transaction(db, uid, transaction_id, body.budgetId))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction or budget not found")


@router.post("/{transaction_id}/reject", response_model=TransactionResponse)
def reject(
    transaction_id: str,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> TransactionResponse:
    try:
        return TransactionResponse(**reject_transaction(db, uid, transaction_id))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")


@router.post("/{transaction_id}/unreject", response_model=TransactionResponse)
def unreject(
    transaction_id: str,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> TransactionResponse:
    try:
        return TransactionResponse(**unreject_transaction(db, uid, transaction_id))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
