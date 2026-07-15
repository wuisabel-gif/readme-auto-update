FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY src /app/src
COPY entrypoint.py /app/entrypoint.py
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/app/entrypoint.py"]

