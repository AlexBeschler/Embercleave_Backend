from functools import lru_cache

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from app.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    settings = get_settings()
    return firebase_admin.initialize_app(options={"projectId": settings.project_id})


def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Verifies the Firebase ID token on every request and returns its
    decoded claims. Routes must always derive the acting user from this,
    never from a client-supplied path/body parameter — see
    architecture.md §3.3.3 / §7.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        return firebase_auth.verify_id_token(credentials.credentials, app=get_firebase_app())
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID token") from exc


def get_current_uid(claims: dict = Depends(get_current_user_claims)) -> str:
    return claims["uid"]
