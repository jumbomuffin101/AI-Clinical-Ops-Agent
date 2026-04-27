FROM python:3.12-slim

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api ./apps/api
COPY data ./data

WORKDIR /app/apps/api

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
