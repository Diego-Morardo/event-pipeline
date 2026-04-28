CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    user_ip TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);