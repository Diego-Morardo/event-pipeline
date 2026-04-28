CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    store_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    user_ip TEXT NOT NULL,
    event_object_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);