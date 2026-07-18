#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "./data/health.db")
if not path.exists():
    raise SystemExit(f"Database not found: {path}")
with sqlite3.connect(path) as con:
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"Database: {path}")
    for table in tables:
        count = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"{table:24} {count:8}")
    pending = con.execute("SELECT COUNT(*) FROM raw_payloads r LEFT JOIN processed_payloads p ON p.payload_id=r.id WHERE p.payload_id IS NULL").fetchone()[0]
    print(f"{'pending_payloads':24} {pending:8}")
