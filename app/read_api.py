from __future__ import annotations

import hmac
import json
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import settings
from .db import connect


class Handler(BaseHTTPRequestHandler):
    server_version = "AppleHealthReadAPI/0.1"

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        return bool(settings.read_api_token) and hmac.compare_digest(supplied, f"Bearer {settings.read_api_token}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json(200, {"ok": True, "service": "read-api", "version": "0.1"})
            return
        if not self._authorized():
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/daily":
                selected = query.get("date", [date.today().isoformat()])[0]
                with connect(settings.database_path, read_only=True) as con:
                    metrics = [dict(r) for r in con.execute("SELECT * FROM daily_metrics WHERE sample_date=? ORDER BY metric", (selected,))]
                    sleep = [dict(r) for r in con.execute("SELECT * FROM sleep_episodes WHERE episode_date=? ORDER BY start_at", (selected,))]
                    workouts = [dict(r) for r in con.execute("SELECT * FROM workouts WHERE substr(start_at,1,10)=? ORDER BY start_at", (selected,))]
                self._json(200, {"date": selected, "metrics": metrics, "sleep": sleep, "workouts": workouts})
            elif parsed.path == "/trend":
                metric = query.get("metric", [""])[0].strip()
                if not metric:
                    raise ValueError("metric is required")
                days = min(max(int(query.get("days", ["30"])[0]), 1), 3650)
                start = (date.today() - timedelta(days=days - 1)).isoformat()
                with connect(settings.database_path, read_only=True) as con:
                    rows = [dict(r) for r in con.execute("SELECT sample_date,metric,unit,sample_count,total_value,average_value,minimum_value,maximum_value,last_value FROM daily_metrics WHERE metric=? AND sample_date>=? ORDER BY sample_date", (metric, start))]
                self._json(200, {"metric": metric, "days": days, "rows": rows})
            elif parsed.path == "/sleep":
                days = min(max(int(query.get("days", ["14"])[0]), 1), 3650)
                start = (date.today() - timedelta(days=days - 1)).isoformat()
                with connect(settings.database_path, read_only=True) as con:
                    rows = [dict(r) for r in con.execute("SELECT * FROM sleep_episodes WHERE episode_date>=? ORDER BY episode_date,start_at", (start,))]
                self._json(200, {"days": days, "rows": rows})
            elif parsed.path == "/workouts":
                days = min(max(int(query.get("days", ["30"])[0]), 1), 3650)
                start = (date.today() - timedelta(days=days - 1)).isoformat()
                with connect(settings.database_path, read_only=True) as con:
                    rows = [dict(r) for r in con.execute("SELECT * FROM workouts WHERE substr(start_at,1,10)>=? ORDER BY start_at DESC", (start,))]
                self._json(200, {"days": days, "rows": rows})
            elif parsed.path == "/completeness":
                days = min(max(int(query.get("days", ["30"])[0]), 1), 3650)
                start = (date.today() - timedelta(days=days - 1)).isoformat()
                with connect(settings.database_path, read_only=True) as con:
                    rows = [dict(r) for r in con.execute("SELECT metric,COUNT(DISTINCT sample_date) AS days_present,MIN(sample_date) AS first_date,MAX(sample_date) AS last_date FROM daily_metrics WHERE sample_date>=? GROUP BY metric ORDER BY metric", (start,))]
                self._json(200, {"window_days": days, "rows": rows})
            else:
                self._json(404, {"ok": False, "error": "not_found"})
        except (ValueError, TypeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", settings.read_api_port), Handler)
    print(f"read-only API listening on port {settings.read_api_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
