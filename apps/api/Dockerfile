FROM python:3.12-slim

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api ./apps/api
COPY data ./data

WORKDIR /app/apps/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
