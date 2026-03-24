FROM python:3.12-slim

WORKDIR /app

COPY py /app/py
COPY server /app/server

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e /app/py fastapi "uvicorn[standard]"

ENV PYTHONPATH=/app:/app/py
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["python", "-m", "server.main"]
