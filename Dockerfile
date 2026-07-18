FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY app ./app
RUN python -m compileall -q app
CMD ["python", "-m", "app.receiver"]
