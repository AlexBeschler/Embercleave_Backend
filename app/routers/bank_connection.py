from fastapi import APIRouter, Depends, Request
from google.cloud import firestore

from app.auth import get_current_uid
from app.firestore_client import get_firestore_client
from app.models import BankConnectionRequest, ConnectionStatusResponse, LinkTokenResponse
from app.services.bank_connection import connect_bank, create_link_token_for_user, disconnect_bank

router = APIRouter(prefix="/bank-connection", tags=["bank-connection"])


@router.post("/link-token", response_model=LinkTokenResponse)
def link_token(request: Request, uid: str = Depends(get_current_uid)) -> LinkTokenResponse:
    webhook_url = str(request.base_url) + "webhooks/plaid"
    return LinkTokenResponse(linkToken=create_link_token_for_user(uid, webhook_url))


@router.post("", response_model=ConnectionStatusResponse)
def connect(
    body: BankConnectionRequest,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> ConnectionStatusResponse:
    return ConnectionStatusResponse(**connect_bank(db, uid, body.publicToken))


@router.post("/disconnect", response_model=ConnectionStatusResponse)
def disconnect(
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> ConnectionStatusResponse:
    return ConnectionStatusResponse(**disconnect_bank(db, uid))
