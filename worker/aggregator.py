import time
from datetime import datetime, timedelta
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

WINDOW_DAYS = 7
SLEEP_SECONDS = 30

AGG_QUERY = text("""
INSERT INTO daily_aggregates (
    store_id,
    date,
    unique_users,
    sessions,
    page_views,
    add_to_carts,
    checkouts_started,
    checkouts_completed
)
SELECT
    e.store_id,
    DATE(e.timestamp) as date,
    COUNT(DISTINCT e.user_ip) as unique_users,
    COUNT(DISTINCT e.session_id) as sessions,
    SUM(CASE WHEN e.event_type = 'page_view' THEN 1 ELSE 0 END) as page_views,
    SUM(CASE WHEN e.event_type = 'add_to_cart' THEN 1 ELSE 0 END) as add_to_carts,
    SUM(CASE WHEN e.event_type = 'checkout_start' THEN 1 ELSE 0 END) as checkouts_started,
    SUM(CASE WHEN e.event_type = 'checkout_success' THEN 1 ELSE 0 END) as checkouts_completed
FROM events e
WHERE e.timestamp >= NOW() - INTERVAL '2 days'
GROUP BY e.store_id, DATE(e.timestamp)
ON CONFLICT (store_id, date) DO UPDATE SET
    unique_users = EXCLUDED.unique_users,
    sessions = EXCLUDED.sessions,
    page_views = EXCLUDED.page_views,
    add_to_carts = EXCLUDED.add_to_carts,
    checkouts_started = EXCLUDED.checkouts_started,
    checkouts_completed = EXCLUDED.checkouts_completed;
""")

def run():
    logger.info("Aggregator started")
    while True:
        try:
            now = datetime.now()
            from_ts = now - timedelta(days=WINDOW_DAYS)

            with engine.begin() as conn:
                conn.execute(AGG_QUERY, {"from_ts": from_ts})

            logger.info("Aggregates recomputed", extra={"from_ts": from_ts.isoformat()})
        except SQLAlchemyError as e:
            logger.error("Aggregator db error", extra={"error": str(e)})

        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    run()