# syntax=docker/dockerfile:1

# Stage 1: build environment
FROM python:3.12-slim AS builder

# System deps for building wheels (cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies into /app/venv
COPY requirements.txt .
RUN python -m venv /app/venv \
    && . /app/venv/bin/activate \
    && pip install --no-cache-dir -U pip wheel \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: final runtime
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN useradd -ms /bin/bash botuser

# Copy venv from builder
COPY --from=builder /app/venv /app/venv

# Copy application
COPY app/ /app/app

# Ensure /data exists (for configs + message_ids.json)
RUN mkdir -p /data && chown -R botuser:botuser /data

USER botuser

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Expose FastAPI admin port
EXPOSE 8080

# Start FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

