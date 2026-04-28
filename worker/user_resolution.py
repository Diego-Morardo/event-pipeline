import time
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.logger import logger

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

SLEEP_SECONDS = 30
BATCH_SIZE = 500

FETCH_EVENTS = text("""
    SELECT DISTINCT session_id, store_id, user_ip
    FROM events
    WHERE session_id NOT IN (
        SELECT session_id FROM sessions
    )
    LIMIT :limit
""")

GET_USER_BY_IP = text("""
    SELECT user_id FROM ip_user_map
    WHERE user_ip = :user_ip AND store_id = :store_id
""")

INSERT_USER = text("""
    INSERT INTO users (id, store_id)
    VALUES (:id, :store_id)
""")

INSERT_IP_MAP = text("""
    INSERT INTO ip_user_map (user_ip, store_id, user_id)
    VALUES (:user_ip, :store_id, :user_id)
    ON CONFLICT (user_ip, store_id) DO NOTHING
""")

INSERT_SESSION = text("""
    INSERT INTO sessions (session_id, store_id, user_id, first_seen, last_seen)
    SELECT
        :session_id,
        :store_id,
        :user_id,
        MIN(timestamp),
        MAX(timestamp)
    FROM events
    WHERE session_id = :session_id
    ON CONFLICT (session_id) DO NOTHING
""")

def resolve_user(conn, store_id: str, user_ip: str) -> str:
    result = conn.execute(GET_USER_BY_IP, {
        "user_ip": user_ip,
        "store_id": store_id
    }).fetchone()

    if result:
        return result[0]
    
    new_user_id = str(uuid.uuid4())

    conn.execute(INSERT_USER, {
        "id": new_user_id,
        "store_id": store_id
    })

    conn.execute(INSERT_IP_MAP, {
        "user_ip": user_ip,
        "store_id": store_id,
        "user_id": new_user_id
    })

    return new_user_id

def run():
    logger.info("User resolution worker started")

    while True:
        try:
            with engine.begin() as conn:
                events = conn.execute(FETCH_EVENTS, {"limit": BATCH_SIZE}).fetchall()

                if not events:
                    logger.info("Not events detected")
                    time.sleep(SLEEP_SECONDS)
                    continue

                for session_id, store_id, user_ip in events:
                    user_id = resolve_user(conn, store_id, user_ip)

                    conn.execute(INSERT_SESSION, {
                        "session_id": session_id,
                        "store_id": store_id,
                        "user_id": user_id
                    })

                logger.info("User resolution batch procesed", extra={"count": len(events)})
        except SQLAlchemyError as e:
            logger.error("User resolution error", extra={"error": str(e)})

        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    run()