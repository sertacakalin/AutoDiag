# AutoDiag backend — FastAPI + sentence-transformers
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/.hf

WORKDIR /app

# Sistem bağımlılıkları (psycopg, torch için).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Veri ve (opsiyonel) modeller compose'da volume olarak bağlanır.
EXPOSE 8000

# Açılışta DB boşsa ingest et, sonra sunucuyu başlat (entrypoint script).
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
