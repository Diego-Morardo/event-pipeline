from dataclasses import dataclass
from datetime import datetime

@dataclass
class Event:
    store_id: str
    event_type: str
    session_id: str
    timestamp: datetime
    user_ip: str
    event_object_id: str