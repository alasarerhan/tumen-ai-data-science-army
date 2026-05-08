FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY platform_api /app/platform_api
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "alembic upgrade head && uvicorn platform_api.asgi:app --host 0.0.0.0 --port 8000"]
