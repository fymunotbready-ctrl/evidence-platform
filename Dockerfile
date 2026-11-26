FROM python:3.14-slim
WORKDIR /app
COPY . .
ENV PYTHONUNBUFFERED=1 EP_DATA=/data/server EVIDENCE_HOME=/data/engine EP_MEMORY_DIR=/data/memory
CMD ["python3", "-m", "server.app"]
