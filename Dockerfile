FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn[standard]

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python scripts/healthcheck.py || exit 1

RUN chmod +x scripts/startup.sh

CMD ["bash", "scripts/startup.sh"]
