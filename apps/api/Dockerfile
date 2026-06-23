FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY apps/api /app/apps/api

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[browser]" \
    && python -m playwright install --with-deps chromium

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "kerislab.main:app", "--host", "0.0.0.0", "--port", "8000"]
