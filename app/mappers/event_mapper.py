from app.domain.models import Event
from app.schemas import EventInput

def to_domain(event_input: EventInput) -> Event:
    return Event(
        store_id=event_input.store_id,
        event_type=event_input.event_type,
        session_id=event_input.session_id,
        timestamp=event_input.timestamp,
        user_ip=event_input.user_ip,
        event_object_id=event_input.event_object_id,
    )