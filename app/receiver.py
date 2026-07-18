from __future__ import annotations

import hashlib
import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import settings
from .db import connect, init_db
from .payloads import utc_now

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("receiver")
ALLOWED_POST_PATHS = {"/", "/health", "/ingest", "/health/ingest"}


class Handler(BaseHTTPRequestHandler):
    server_version = "AppleHealthReceiver/0.1"

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/healthz"}:
            self._json(200, {"ok": True, "service": "receiver", "version": "0.1"})
        else:
            self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if self.path not in ALLOWED_POST_PATHS:
            self._json(404, {"ok": False, "error": "not_found"})
            return
        if not settings.ingest_token:
            self._json(503, {"ok": False, "error": "server_token_not_configured"})
            return
        supplied = self.headers.get("X-Health-Token", "")
        if not hmac.compare_digest(supplied, settings.ingest_token):
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"ok": False, "error": "invalid_content_length"})
            return
        if length <= 0 or length > settings.max_body_bytes:
            self._json(413, {"ok": False, "error": "invalid_body_size"})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"ok": False, "error": "json_object_required"})
            return
        payload_id = hashlib.sha256(raw).hexdigest()
        with connect(settings.database_path) as con:
            cursor = con.execute(
                "INSERT OR IGNORE INTO raw_payloads(id, received_at, body) VALUES (?, ?, ?)",
                (payload_id, utc_now(), raw.decode("utf-8")),
            )
            con.commit()
        duplicate = cursor.rowcount == 0
        LOG.info("payload=%s duplicate=%s bytes=%s", payload_id[:12], duplicate, length)
        self._json(202, {"ok": True, "payload_id": payload_id, "duplicate": duplicate})

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    init_db(settings.database_path)
    server = ThreadingHTTPServer(("0.0.0.0", settings.receiver_port), Handler)
    LOG.info("receiver listening on port %s", settings.receiver_port)
    server.serve_forever()


if __name__ == "__main__":
    main()
