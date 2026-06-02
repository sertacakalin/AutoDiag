#!/usr/bin/env bash
# DB hazır olana kadar bekle, korpus boşsa ingest et, sonra API'yi başlat.
set -e

echo "[entrypoint] DB bekleniyor..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
url = os.environ["DATABASE_URL"]
for i in range(60):
    try:
        create_engine(url).connect().execute(text("SELECT 1"))
        print("[entrypoint] DB hazır.")
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("[entrypoint] DB'ye ulaşılamadı.")
PY

# Korpus boşsa yükle (idempotent).
python - <<'PY'
from app.db import SessionLocal
from sqlalchemy import select, func
try:
    from app.models import Fault
    with SessionLocal() as db:
        n = db.scalar(select(func.count()).select_from(Fault)) or 0
except Exception:
    n = 0
import sys
sys.exit(0 if n > 0 else 7)
PY
if [ $? -eq 7 ]; then
  echo "[entrypoint] Korpus yükleniyor (ingestion)..."
  python -m app.services.ingestion --csv /data/faults_dataset.csv
else
  echo "[entrypoint] Korpus zaten dolu, ingest atlanıyor."
fi

echo "[entrypoint] API başlatılıyor."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
