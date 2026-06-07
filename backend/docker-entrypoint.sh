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

# Korpus boşsa yükle (idempotent). Sayım kontrolünü `if` koşuluna alıyoruz:
# `set -e` yalnız koşulda KULLANILMAYAN komutlarda devreye girer; if-condition
# içindeki non-zero exit script'i öldürmez. (Tablo henüz yoksa count hata verir
# → except n=0 → "dolu değil" → ingest çalışır, init_db tabloları kurar.)
if python - <<'PY'
import sys
from app.db import SessionLocal
from sqlalchemy import select, func
try:
    from app.models import Fault
    with SessionLocal() as db:
        n = db.scalar(select(func.count()).select_from(Fault)) or 0
except Exception:
    n = 0
sys.exit(0 if n > 0 else 1)   # 0 = dolu (ingest atla), 1 = boş (ingest et)
PY
then
  echo "[entrypoint] Korpus zaten dolu, ingest atlanıyor."
else
  echo "[entrypoint] Korpus yükleniyor (ingestion)..."
  python -m app.services.ingestion --csv /data/faults_dataset.csv
fi

echo "[entrypoint] API başlatılıyor."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
