FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir flask gunicorn

COPY server.py /app/server.py
COPY index.html /app/index.html

RUN mkdir -p /tmp/hls_streams && chmod -R 777 /tmp/hls_streams /app

ENV PORT=7860
ENV HLS_DIR=/tmp/hls_streams
ENV DB_FILE=/tmp/db.json

EXPOSE 7860

CMD ["gunicorn", "--workers", "1", "--threads", "12", "--timeout", "120", "-b", "0.0.0.0:7860", "server:app"]
