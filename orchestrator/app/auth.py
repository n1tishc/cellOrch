"""Firebase authentication dependency (disabled only for local development)."""
from fastapi import HTTPException, Request
from firebase_admin import auth, credentials, get_app, initialize_app

from .config import settings


def _initialize() -> None:
    try:
        get_app()
    except ValueError:
        initialize_app(credentials.ApplicationDefault())


def get_current_user(request: Request) -> dict:
    if not settings.firebase_auth_enabled:
        return {"uid": "local-development"}
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        _initialize()
        return auth.verify_id_token(header.removeprefix("Bearer "))
    except Exception as exc:
        raise HTTPException(401, "invalid Firebase token") from exc
