import asyncio
import json

from app import engine
from app.main import stream_runs
from app.run_events import publish, subscribe, unsubscribe
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


def test_run_stream_uses_valid_sse_frame():
    event = {"run_id": 7, "type": "step_started", "message": "Seed"}

    async def receive_event():
        response = await stream_runs()
        next_chunk = asyncio.create_task(anext(response.body_iterator))
        await asyncio.sleep(0)
        publish(event)
        chunk = await asyncio.wait_for(next_chunk, timeout=1)
        await response.body_iterator.aclose()
        return chunk

    assert asyncio.run(receive_event()) == "data: " + json.dumps(event) + "\n\n"
