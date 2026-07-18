from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv("DATABASE_PATH", "/data/health.db")
    ingest_token: str = os.getenv("HEALTH_INGEST_TOKEN", "")
    read_api_token: str = os.getenv("READ_API_TOKEN", "")
    receiver_port: int = int(os.getenv("RECEIVER_PORT", "8765"))
    read_api_port: int = int(os.getenv("READ_API_PORT", "8770"))
    max_body_bytes: int = int(os.getenv("MAX_BODY_BYTES", str(20 * 1024 * 1024)))
    normalizer_interval_seconds: int = int(os.getenv("NORMALIZER_INTERVAL_SECONDS", "60"))
    raw_retention_days: int = int(os.getenv("RAW_RETENTION_DAYS", "30"))


settings = Settings()
