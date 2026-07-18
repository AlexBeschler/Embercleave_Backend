from fastapi import APIRouter, Depends
from google.cloud import firestore

from app.auth import get_current_user_claims
from app.firestore_client import get_firestore_client
from app.models import BootstrapResponse
from app.services.users import bootstrap_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    claims: dict = Depends(get_current_user_claims),
    db: firestore.Client = Depends(get_firestore_client),
) -> BootstrapResponse:
    uid = claims["uid"]
    data = bootstrap_user(db, uid, email=claims.get("email"))
    return BootstrapResponse(
        uid=uid,
        email=data.get("email"),
        connectionStatus=data["connectionStatus"],
        activePeriodId=data["activePeriodId"],
    )
