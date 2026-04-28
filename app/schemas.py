from pydantic import RootModel, BaseModel
from typing import Literal, List
from datetime import datetime

EventType = Literal[
    "page_view",
    "add_to_cart",
    "checkout_start",
    "checkout_success"
]

class EventInput(BaseModel):
    store_id: str
    event_type: EventType
    session_id: str
    timestamp: datetime
    user_ip: str
    event_object_id: str

class BatchEvents(RootModel):
    root: List[EventInput]