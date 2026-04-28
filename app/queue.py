import json
import redis
import hashlib
from typing import Dict, Any
from app.config import settings
from app.utils.serialization import to_json_safe

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
STREAM_NAME = "events_stream"

def generate_event_id(event: dict) -> str:
    safe_event = to_json_safe(event)
    raw = json.dumps(safe_event, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def push_event(event: Dict[str, Any]) -> None:
    safe_event = to_json_safe(event)
    safe_event["event_id"] = generate_event_id(safe_event)
    redis_client.xadd(STREAM_NAME, {"data": json.dumps(safe_event)})