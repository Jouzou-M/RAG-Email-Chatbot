# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# Runtime stage
FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/

RUN mkdir -p data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000 8501
