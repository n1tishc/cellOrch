from app import engine
from app.run_events import subscribe, unsubscribe
from sqlmodel import Session


def test_engine_log_publishes_dashboard_event():
    queue = subscribe()
    try:
        with Session() as session:
            engine.log(session, 7, "step_started", "Seed")
        event = queue.get_nowait()
    finally:
        unsubscribe(queue)

    assert event["run_id"] == 7
    assert event["type"] == "step_started"
