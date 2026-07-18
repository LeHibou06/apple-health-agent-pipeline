#!/usr/bin/env python3
import secrets

print("HEALTH_INGEST_TOKEN=" + secrets.token_urlsafe(48))
print("READ_API_TOKEN=" + secrets.token_urlsafe(48))
