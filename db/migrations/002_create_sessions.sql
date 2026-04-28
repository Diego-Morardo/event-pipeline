CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    user_id TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP
);