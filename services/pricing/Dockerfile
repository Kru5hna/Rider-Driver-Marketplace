FROM python:3.11-slim

WORKDIR /app

COPY proto/ /app/proto/
COPY services/pricing/ /app/services/pricing/

RUN pip install --no-cache-dir grpcio grpcio-tools

EXPOSE 50051

CMD ["python", "services/pricing/server.py"]
