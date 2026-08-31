FROM python:3.11-slim

WORKDIR /app

COPY proto/ /app/proto/
COPY services/ /app/services/

RUN pip install --no-cache-dir fastapi uvicorn sqlalchemy pymysql grpcio grpcio-tools pydantic

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "services.dispatch.main:app", "--host", "0.0.0.0", "--port", "8000"]

