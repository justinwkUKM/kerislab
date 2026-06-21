FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/
RUN pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" "pydantic>=2.8.0"
COPY apps/api /app/apps/api
ENV PYTHONPATH=/app/apps/api
CMD ["uvicorn", "kerislab.main:app", "--host", "0.0.0.0", "--port", "8000"]

