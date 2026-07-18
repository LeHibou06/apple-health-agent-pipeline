from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

APPLE_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S %z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%SZ",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(*parts: Any) -> str:
    encoded = "\x1f".join("" if p is None else str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in APPLE_DATE_FORMATS:
        try:
            parsed = datetime.strptime(str(value), fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def iso_datetime(value: Any) -> str | None:
    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else None


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def iter_metrics(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    data = payload.get("data", payload)
    metrics = data.get("metrics", []) if isinstance(data, dict) else []
    return metrics if isinstance(metrics, list) else []


def iter_workouts(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    data = payload.get("data", payload)
    workouts = data.get("workouts", []) if isinstance(data, dict) else []
    return workouts if isinstance(workouts, list) else []
