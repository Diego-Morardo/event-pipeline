import json
import redis
import time
import uuid
from typing import List, Dict
from app.config import settings
from app.logger import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

STREAM = "events_stream"
GROUP = "workers"
CONSUMER = f"consumer-{uuid.uuid4()}"

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

def init_group():
    try:
        redis_client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError:
        pass

def process_batch(event_data: List[Dict[str, str]]) -> None:
    query = text("""
        INSERT INTO events (
            store_id, event_type, session_id, timestamp, user_ip, event_object_id         
        ) VALUES (
            :store_id, :event_type, :session_id, :timestamp, :user_ip, :event_object_id         
        ) ON CONFLICT (event_id) DO NOTHING
    """)
    with engine.begin() as conn:
        conn.execute(query, event_data)

def run() -> None:
    init_group()

    while True:
        response = redis_client.xreadgroup(
            GROUP,
            CONSUMER,
            {STREAM: ">"},
            count=100,
            block=5000
        )

        if not response:
            continue

        for _, messages in response:
            batch: List[dict] = []
            ids: List[str] = []

            for msg_id, msg in messages:
                try:
                    data = json.loads(msg["data"])
                    batch.append(data)
                    ids.append(msg_id)
                except json.JSONDecodeError:
                    logger.error(f"Poison pill", extra={"msg_id": msg_id})
                    redis_client.xack(STREAM, GROUP, msg_id)

            if not batch:
                continue

            try:
                process_batch(batch)
                for msg_id in ids:
                    redis_client.xack(STREAM, GROUP, msg_id)
            except SQLAlchemyError:
                logger.error(f"Batch failed, fallback to single insert")

                for event, msg_id in zip(batch, ids):
                    try:
                        process_batch([event])
                        redis_client.xack(STREAM, GROUP, msg_id)
                    except SQLAlchemyError as e:
                        logger.error("Failed event", extra={"event": event, "error": str(e)})
                        redis_client.xadd("dead_letter_stream", {"data": json.dumps(event)})
                        redis_client.xack(STREAM, GROUP, msg_id)
        
        time.sleep(0.1)

if __name__ == "__main__":
    run()