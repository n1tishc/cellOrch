"""Best-effort asynchronous webhook delivery."""
import json
import threading
import httpx
from sqlmodel import Session, select
from .models import Webhook
from .logging_config import get_logger
logger = get_logger(__name__)

def fire_webhooks(session: Session, event_type: str, payload: dict) -> None:
    hooks = [hook for hook in session.exec(select(Webhook).where(Webhook.active == True)).all() if event_type in json.loads(hook.events)]
    for hook in hooks:
        threading.Thread(target=_post, args=(hook.url, payload), daemon=True).start()

def _post(url: str, payload: dict) -> None:
    try: httpx.post(url, json=payload, timeout=5.0).raise_for_status()
    except httpx.HTTPError as exc: logger.warning("webhook_failed", extra={"error": str(exc), "event_type": "webhook_error"})
