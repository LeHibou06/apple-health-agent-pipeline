from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import timedelta
from typing import Any

from .config import settings
from .db import connect, init_db
from .payloads import as_float, compact_json, first, iso_datetime, iter_metrics, iter_workouts, parse_datetime, stable_id, utc_now

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("normalizer")

SUM_METRICS = {"active_energy", "step_count", "walking_running_distance", "dietary_energy", "dietary_protein", "dietary_carbohydrates", "dietary_fat_total", "dietary_fiber", "dietary_water", "mindful_minutes"}
LAST_METRICS = {"weight_body_mass", "waist_circumference", "body_fat_percentage", "body_mass_index", "lean_body_mass"}
SLEEP_STAGE_MAP = {"core": "core", "asleepcore": "core", "deep": "deep", "asleepdeep": "deep", "rem": "rem", "asleeprem": "rem", "awake": "awake", "inbed": "awake", "asleep": "asleep_unspecified", "asleepunspecified": "asleep_unspecified"}


def _metric_name(metric: dict[str, Any]) -> str | None:
    value = first(metric, "name", "metric", "type")
    return str(value).strip() if value else None


def _entries(metric: dict[str, Any]) -> list[dict[str, Any]]:
    data = metric.get("data", [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def insert_general_samples(con, payload_id: str, payload: dict[str, Any]) -> int:
    inserted = 0
    for metric in iter_metrics(payload):
        if not isinstance(metric, dict):
            continue
        name = _metric_name(metric)
        if not name or name == "sleep_analysis":
            continue
        for entry in _entries(metric):
            sample_at = iso_datetime(first(entry, "date", "sampleDate", "startDate", "start", "timestamp"))
            parsed = parse_datetime(sample_at)
            if not parsed:
                continue
            unit = str(first(entry, "unit", "units") or first(metric, "unit", "units") or "")
            qty = as_float(first(entry, "qty", "value", "quantity"))
            avg_value = as_float(first(entry, "Avg", "avg", "average"))
            min_value = as_float(first(entry, "Min", "min", "minimum"))
            max_value = as_float(first(entry, "Max", "max", "maximum"))
            source = str(first(entry, "source", "sourceName", "device") or "")
            sample_id = stable_id(name, sample_at, unit, qty, avg_value, min_value, max_value, source)
            cursor = con.execute("""
                INSERT OR IGNORE INTO health_samples(
                    id, payload_id, metric, sample_at, sample_date, unit, qty,
                    avg_value, min_value, max_value, source, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sample_id, payload_id, name, sample_at, parsed.date().isoformat(), unit, qty, avg_value, min_value, max_value, source, compact_json(entry)))
            inserted += max(cursor.rowcount, 0)
    return inserted


def insert_sleep_segments(con, payload_id: str, payload: dict[str, Any]) -> int:
    inserted = 0
    for metric in iter_metrics(payload):
        if not isinstance(metric, dict) or _metric_name(metric) != "sleep_analysis":
            continue
        for entry in _entries(metric):
            start_at = iso_datetime(first(entry, "startDate", "start", "date"))
            end_at = iso_datetime(first(entry, "endDate", "end"))
            start, end = parse_datetime(start_at), parse_datetime(end_at)
            if not start or not end or end <= start:
                continue
            raw_stage = first(entry, "value", "stage", "sleepStage")
            compact = "".join(ch for ch in str(raw_stage or "").lower() if ch.isalnum())
            stage = SLEEP_STAGE_MAP.get(compact, "asleep_unspecified")
            source = str(first(entry, "source", "sourceName", "device") or "")
            segment_id = stable_id(start_at, end_at, raw_stage, source)
            cursor = con.execute("""
                INSERT OR IGNORE INTO sleep_segments(
                    id, payload_id, start_at, end_at, duration_minutes,
                    source, stage_raw, stage_normalized
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (segment_id, payload_id, start_at, end_at, (end - start).total_seconds() / 60.0, source, str(raw_stage or ""), stage))
            inserted += max(cursor.rowcount, 0)
    return inserted


def _value_and_unit(value: Any) -> tuple[float | None, str]:
    if isinstance(value, dict):
        return as_float(first(value, "qty", "value", "quantity")), str(first(value, "unit", "units") or "")
    return as_float(value), ""


def insert_workouts(con, payload_id: str, payload: dict[str, Any]) -> int:
    inserted = 0
    for workout in iter_workouts(payload):
        if not isinstance(workout, dict):
            continue
        start_at = iso_datetime(first(workout, "start", "startDate", "date"))
        if not start_at:
            continue
        end_at = iso_datetime(first(workout, "end", "endDate"))
        workout_id = str(first(workout, "id", "uuid") or stable_id(start_at, end_at, compact_json(workout)))
        distance, distance_unit = _value_and_unit(first(workout, "distance"))
        energy, energy_unit = _value_and_unit(first(workout, "activeEnergyBurned", "activeEnergy"))
        hr = workout.get("heartRate", {}) if isinstance(workout.get("heartRate"), dict) else {}
        cursor = con.execute("""
            INSERT OR IGNORE INTO workouts(
                id, payload_id, workout_type, name, start_at, end_at,
                duration_seconds, distance, distance_unit, energy, energy_unit,
                heart_rate_average, heart_rate_minimum, heart_rate_maximum,
                elevation_up, is_indoor, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (workout_id, payload_id, str(first(workout, "workoutActivityType", "type") or ""), str(first(workout, "name", "title") or ""), start_at, end_at, as_float(first(workout, "duration", "durationSeconds")), distance, distance_unit, energy, energy_unit, as_float(first(hr, "Avg", "avg", "average") or first(workout, "heartRateAverage")), as_float(first(hr, "Min", "min", "minimum") or first(workout, "heartRateMinimum")), as_float(first(hr, "Max", "max", "maximum") or first(workout, "heartRateMaximum")), as_float(first(workout, "elevationUp", "elevationGain")), 1 if bool(first(workout, "isIndoor")) else 0, compact_json(workout)))
        inserted += max(cursor.rowcount, 0)
    return inserted


def rebuild_daily_metrics(con) -> None:
    con.execute("DELETE FROM daily_metrics")
    groups = con.execute("SELECT DISTINCT sample_date, metric, COALESCE(unit, '') FROM health_samples").fetchall()
    updated_at = utc_now()
    for date_value, metric, unit in groups:
        rows = con.execute("""
            SELECT qty, avg_value, min_value, max_value, sample_at
            FROM health_samples
            WHERE sample_date = ? AND metric = ? AND COALESCE(unit, '') = ?
            ORDER BY sample_at
        """, (date_value, metric, unit)).fetchall()
        qty_values = [r[0] for r in rows if r[0] is not None]
        avg_values = [r[1] for r in rows if r[1] is not None]
        min_values = [r[2] for r in rows if r[2] is not None]
        max_values = [r[3] for r in rows if r[3] is not None]
        source_values = avg_values or qty_values
        total = sum(qty_values) if metric in SUM_METRICS and qty_values else None
        average = sum(source_values) / len(source_values) if source_values and metric not in LAST_METRICS else None
        minimum = min(min_values or source_values) if source_values and metric not in LAST_METRICS else None
        maximum = max(max_values or source_values) if source_values and metric not in LAST_METRICS else None
        last_value = qty_values[-1] if metric in LAST_METRICS and qty_values else None
        con.execute("""
            INSERT INTO daily_metrics(
                sample_date, metric, unit, sample_count, total_value,
                average_value, minimum_value, maximum_value, last_value, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_value, metric, unit, len(rows), total, average, minimum, maximum, last_value, updated_at))


def rebuild_sleep_episodes(con, gap_minutes: int = 30, nap_threshold_minutes: int = 180) -> None:
    rows = con.execute("SELECT start_at, end_at, duration_minutes, stage_normalized FROM sleep_segments ORDER BY start_at").fetchall()
    con.execute("DELETE FROM sleep_episodes")
    episodes: list[list[Any]] = []
    for row in rows:
        start = parse_datetime(row[0])
        end = parse_datetime(row[1])
        if not start or not end:
            continue
        if not episodes:
            episodes.append([row])
            continue
        previous_end = parse_datetime(episodes[-1][-1][1])
        if previous_end and start - previous_end < timedelta(minutes=gap_minutes):
            episodes[-1].append(row)
        else:
            episodes.append([row])
    updated_at = utc_now()
    for segments in episodes:
        start, end = parse_datetime(segments[0][0]), parse_datetime(segments[-1][1])
        if not start or not end:
            continue
        totals = {"awake": 0.0, "core": 0.0, "deep": 0.0, "rem": 0.0, "asleep_unspecified": 0.0}
        awakenings = awakenings_5m = 0
        for segment in segments:
            stage, duration = segment[3], float(segment[2])
            totals[stage] = totals.get(stage, 0.0) + duration
            if stage == "awake":
                awakenings += 1
                if duration >= 5:
                    awakenings_5m += 1
        sleep_minutes = totals["core"] + totals["deep"] + totals["rem"] + totals["asleep_unspecified"]
        elapsed = (end - start).total_seconds() / 60.0
        episode_type = "nap" if sleep_minutes < nap_threshold_minutes else "night"
        episode_date = (start.date() if episode_type == "nap" else end.date()).isoformat()
        con.execute("""
            INSERT INTO sleep_episodes(
                id, episode_date, episode_type, start_at, end_at,
                total_sleep_minutes, awake_minutes, core_minutes, deep_minutes,
                rem_minutes, unspecified_minutes, efficiency, awakenings,
                awakenings_5m, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (stable_id(start.isoformat(), end.isoformat(), episode_type), episode_date, episode_type, start.isoformat(), end.isoformat(), sleep_minutes, totals["awake"], totals["core"], totals["deep"], totals["rem"], totals["asleep_unspecified"], sleep_minutes / elapsed if elapsed > 0 else None, awakenings, awakenings_5m, updated_at))


def process_one(database_path: str) -> bool:
    with connect(database_path) as con:
        row = con.execute("""
            SELECT r.id, r.body FROM raw_payloads r
            LEFT JOIN processed_payloads p ON p.payload_id = r.id
            WHERE p.payload_id IS NULL ORDER BY r.received_at LIMIT 1
        """).fetchone()
        if not row:
            return False
        payload_id, body = row[0], row[1]
        try:
            payload = json.loads(body)
            general = insert_general_samples(con, payload_id, payload)
            sleep = insert_sleep_segments(con, payload_id, payload)
            workouts = insert_workouts(con, payload_id, payload)
            rebuild_daily_metrics(con)
            rebuild_sleep_episodes(con)
            con.execute("INSERT INTO processed_payloads(payload_id, processed_at, status, error) VALUES (?, ?, 'ok', NULL)", (payload_id, utc_now()))
            con.commit()
            LOG.info("processed=%s samples=%s sleep=%s workouts=%s", payload_id[:12], general, sleep, workouts)
        except Exception as exc:
            con.execute("INSERT OR REPLACE INTO processed_payloads(payload_id, processed_at, status, error) VALUES (?, ?, 'error', ?)", (payload_id, utc_now(), str(exc)[:1000]))
            con.commit()
            LOG.exception("failed payload=%s", payload_id[:12])
        return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    init_db(settings.database_path)
    while True:
        processed_any = False
        while process_one(settings.database_path):
            processed_any = True
        if args.once:
            return
        if not processed_any:
            time.sleep(settings.normalizer_interval_seconds)


if __name__ == "__main__":
    main()
