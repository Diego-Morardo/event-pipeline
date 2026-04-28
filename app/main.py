from fastapi import FastAPI, HTTPException, Response, Query
from sqlalchemy import create_engine, text
from redis.exceptions import RedisError
from typing import List
from dataclasses import asdict
from app.schemas import EventInput
from app.mappers.event_mapper import to_domain
from app.queue import push_event
from app.logger import logger
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/events")
def ingest_event(event_input: EventInput) -> Response:
    try:
        event = to_domain(event_input)
        # push_event(event.model_dump(mode="json"))
        push_event(asdict(event))
        return Response(status_code=202)
    except RedisError as e:
        logger.error("Redis error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Queue Error")

@app.post("/events/batch")
def ingest_batch(events: List[EventInput]) -> Response:
    try:
        for event_input in events:
            event = to_domain(event_input)
            # push_event(event.model_dump(mode="json"))
            push_event(asdict(event))
        return Response(status_code=202)
    except RedisError as e:
        logger.error("Redis error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Queue Error")
    
# Reporting API
@app.get("/stores/{store_id}/report")
def get_report(
    store_id: str,
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to")
) -> List[dict]:
    query = text("""
        SELECT * FROM daily_aggregates
        WHERE store_id = :store_id
        AND date BETWEEN :from_date AND :to_date
        ORDER BY date ASC
    """)

    with engine.begin() as conn:
        result = conn.execute(query, {
            "store_id": store_id,
            "from_date": from_date,
            "to_date": to_date
        }).mappings().all()

    return list(result)

# Journey endpoint
@app.get("/conversions/{checkout_id}/journey")
def get_journey(checkout_id: str):
    # Step 1: find checkout_success event
    checkout_query = text("""
        SELECT store_id, session_id, timestamp
        FROM events
        WHERE event_type = 'checkout_success'
        AND event_object_id = :checkout_id
        LIMIT 1
    """)

    with engine.begin() as conn:
        checkout_event = conn.execute(checkout_query, {
            "checkout_id": checkout_id
        }).fetchone()

        if not checkout_event:
            raise HTTPException(status_code=404, detail="Checkout not found")

        store_id, session_id, conversion_ts = checkout_event

        # Step 2: get user_id from session
        user_query = text("""
            SELECT user_id FROM sessions
            WHERE session_id = :session_id
        """)

        user_result = conn.execute(user_query, {
            "session_id": session_id
        }).fetchone()

        if not user_result:
            raise HTTPException(status_code=404, detail="User not found for session")

        user_id = user_result[0]

        # Step 3: get all sessions for user
        sessions_query = text("""
            SELECT session_id, first_seen, last_seen
            FROM sessions
            WHERE user_id = :user_id AND store_id = :store_id
            ORDER BY first_seen ASC
        """)

        sessions = conn.execute(sessions_query, {
            "user_id": user_id,
            "store_id": store_id
        }).fetchall()

        # Step 4: get all events for those sessions
        session_ids = [s[0] for s in sessions]

        if not session_ids:
            return {"checkout_id": checkout_id, "sessions": []}

        events_query = text("""
            SELECT session_id, event_type, event_object_id, timestamp
            FROM events
            WHERE session_id = ANY(:session_ids)
            ORDER BY timestamp ASC
        """)

        events = conn.execute(events_query, {
            "session_ids": session_ids
        }).fetchall()

    # Step 5: group events by session
    session_map = {s[0]: {
        "session_id": s[0],
        "first_seen": s[1],
        "last_seen": s[2],
        "events": []
    } for s in sessions}

    for session_id, event_type, object_id, ts in events:
        session_map[session_id]["events"].append({
            "type": event_type,
            "object_id": object_id,
            "timestamp": ts
        })

    # Step 6: build response
    return {
        "checkout_id": checkout_id,
        "store_id": store_id,
        "conversion_date": conversion_ts,
        "sessions": list(session_map.values())
    }