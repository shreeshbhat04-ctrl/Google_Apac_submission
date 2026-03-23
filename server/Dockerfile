FROM python:3.12-slim

WORKDIR /app

COPY py /app/py
COPY server /app/server

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e /app/py fastapi "uvicorn[standard]"

ENV PYTHONPATH=/app:/app/py
ENV PORT=8080

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
