# Exporter setup notes

The examples follow a common Health Auto Export JSON v2 shape but the repository is not tied to one exporter.

Suggested automations:

- sleep analysis on its own;
- general activity, cardio, respiratory, and body metrics;
- workouts as separate objects, initially without detailed GPS routes.

Use incremental export mode where available.

```text
POST http://PRIVATE_SERVER_ADDRESS:8765/health
X-Health-Token: <HEALTH_INGEST_TOKEN>
Content-Type: application/json
```

Use a VPN or private overlay network. iOS background execution is opportunistic: an interval is a requested cadence, not a guaranteed clock schedule.
