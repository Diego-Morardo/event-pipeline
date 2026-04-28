CREATE INDEX idx_store_timestamp ON events(store_id, timestamp);
CREATE INDEX idx_session ON events(session_id);
CREATE INDEX idx_events_store_date ON events(store_id, timestamp);
CREATE INDEX idx_events_session ON events(session_id, timestamp);
CREATE INDEX idx_events_type_object ON events(event_type, event_object_id);

CREATE INDEX idx_daily_store_date ON daily_aggregates(store_id, date);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);