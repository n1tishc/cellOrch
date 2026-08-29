"""Best-effort asynchronous webhook delivery."""
import json
import threading
import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from .models import Webhook
from .logging_config import get_logger
logger = get_logger(__name__)

def fire_webhooks(session: Session, event_type: str, payload: dict) -> None:
    """Schedule matching active webhook deliveries without blocking a tick."""
    try:
        hooks = session.exec(select(Webhook).where(Webhook.active == True)).all()  # noqa: E712
    except SQLAlchemyError as exc:
        logger.warning("webhook_selection_failed", extra={"error": str(exc), "event_type": "webhook_error"})
        return
    for hook in hooks:
        try:
            subscribed_events = json.loads(hook.events)
        except json.JSONDecodeError:
            logger.warning("webhook_events_invalid", extra={"event_type": "webhook_error", "webhook_id": hook.id})
            continue
        if event_type in subscribed_events:
            dispatch_webhook(hook.url, payload)


def dispatch_webhook(url: str, payload: dict) -> None:
    threading.Thread(target=_post, args=(url, payload), daemon=True).start()

def _post(url: str, payload: dict) -> None:
    try: httpx.post(url, json=payload, timeout=5.0).raise_for_status()
    except httpx.HTTPError as exc: logger.warning("webhook_failed", extra={"error": str(exc), "event_type": "webhook_error"})
