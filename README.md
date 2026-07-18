# Apple Health Agent Pipeline

A small, self-hosted pipeline that turns Apple Health exports into a normalized SQLite database that an AI assistant can query through controlled, read-only tools.

The project is intentionally generic. It contains no personal paths, IP addresses, tokens, health records, or assistant-specific configuration.

> This is an experimental personal-data project, not a medical device. It must not be used for diagnosis or emergency monitoring.

## Idea

```text
Apple Health
    ↓
iPhone export app
    ↓
private authenticated transport
    ↓
receiver
    ↓
raw JSON + deduplication
    ↓
normalizer
    ↓
SQLite health database
    ↓
read-only API or MCP adapter
    ↓
health-analysis agent
    ↓
main personal assistant
```

The important separation is:

- code performs reproducible calculations;
- a specialist agent interprets the results;
- the main assistant places them in the user's broader context.

The language model never receives unrestricted SQL access and does not invent statistics from raw samples.

## What is included

- authenticated HTTP receiver for JSON exports;
- SHA-256 deduplication of incoming payloads;
- asynchronous normalization in a separate worker;
- SQLite storage for raw payloads, health samples, daily metrics, sleep episodes, and workouts;
- aggregation rules for cumulative, physiological, and body-measurement metrics;
- small read-only HTTP API suitable for an agent adapter or MCP wrapper;
- Docker Compose setup;
- sample payloads, tests, backup and inspection scripts.

The sample parser targets the general shape of Health Auto Export JSON v2, while keeping the normalization code easy to adapt to other exporters.

## Quick start

Requirements:

- Docker with Docker Compose;
- an iPhone export application capable of sending Apple Health data as JSON;
- a private network or authenticated reverse proxy between the phone and the server.

```bash
cp .env.example .env
python3 scripts/generate_token.py
```

Copy the generated values into `.env`, then start the stack:

```bash
docker compose up -d --build
```

Check the receiver:

```bash
curl http://127.0.0.1:8765/healthz
```

Check the read-only API:

```bash
curl -H "Authorization: Bearer YOUR_READ_API_TOKEN" \
  "http://127.0.0.1:8770/daily?date=2026-01-01"
```

## Exporter configuration

Configure the iPhone exporter to POST JSON to:

```text
http://PRIVATE_SERVER_ADDRESS:8765/health
```

Add the header:

```text
X-Health-Token: <HEALTH_INGEST_TOKEN>
```

Recommended logical separation:

1. sleep data;
2. general metrics;
3. workouts.

Use incremental export mode when the exporter supports it. Large historical imports should be staged separately and merged only after deduplication.

See [docs/HEALTH_AUTO_EXPORT.md](docs/HEALTH_AUTO_EXPORT.md).

## Private transport

The receiver intentionally does not provide public TLS termination. Put it behind a private network or trusted reverse proxy, for example:

- Tailscale;
- WireGuard;
- a private VPN;
- an HTTPS reverse proxy with strict authentication.

Do not expose the receiver directly to the public internet.

## Data model

The SQLite database contains:

- `raw_payloads`: immutable incoming JSON payloads;
- `processed_payloads`: normalization queue state;
- `health_samples`: normalized measurements;
- `daily_metrics`: daily totals, averages, extrema, or latest values;
- `sleep_segments`: normalized sleep stages;
- `sleep_episodes`: grouped nights and naps;
- `workouts`: one row per workout session.

Aggregation rules are metric-aware:

- cumulative metrics such as steps, distance, and active energy are summed;
- physiological metrics use averages and extrema;
- body measurements use the latest valid value of the day;
- workouts remain individual sessions;
- sleep segments are grouped into nights and naps.

## Read-only agent access

The included API exposes controlled queries only:

```text
GET /daily?date=YYYY-MM-DD
GET /trend?metric=step_count&days=30
GET /sleep?days=14
GET /workouts?days=30
GET /completeness?days=30
```

It opens SQLite in read-only mode and does not accept arbitrary SQL. A production agent can consume these endpoints directly or wrap them in MCP tools such as:

```text
get_daily_summary
get_metric_trend
get_sleep_history
get_workouts
check_data_completeness
```

## Local development

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

Run one normalization pass:

```bash
DATABASE_PATH=./data/health.db python3 -m app.normalizer --once
```

Inspect the database:

```bash
python3 scripts/inspect_db.py ./data/health.db
```

Create a backup:

```bash
scripts/backup_db.sh ./data/health.db ./backups
```

## Privacy

Health data is highly sensitive. Before using this project:

- keep `.env` and database files out of Git;
- use encrypted backups;
- restrict filesystem permissions;
- expose the receiver only through a private or authenticated channel;
- give agents read-only, bounded tools;
- define a retention policy for raw JSON payloads;
- never send health data to a model provider without informed consent.

See [docs/PRIVACY.md](docs/PRIVACY.md).

## Status

This repository is a reference implementation and starting point. Export formats vary between applications and versions, so inspect sample payloads from your own exporter before relying on a field in production.

## License

MIT. See [LICENSE](LICENSE).
