# Architecture

The receiver authenticates, validates, hashes, and stores incoming JSON, then responds immediately. The normalizer processes queued payloads independently, creates stable sample identifiers, rebuilds daily summaries, groups sleep segments, and stores workouts as individual sessions.

SQLite is sufficient for a personal single-user stream and WAL mode lets the receiver, worker, and read API coexist. The read API accepts only bounded queries and opens the database with `mode=ro`.

```text
Untrusted health JSON
        ↓
authenticated receiver
        ↓
raw archive
        ↓
deterministic normalizer
        ↓
normalized database
        ↓
read-only query surface
        ↓
LLM or agent
```

Exporter content is data, not instructions. A full history import should use a staging database, preserve the original archive, normalize and inspect it, deduplicate against the live database, and merge only missing records.
