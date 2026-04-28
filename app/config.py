import os

class Settings:
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@db:5432/events"
    )

settings = Settings()