"""Faz 4 — Veri yükleme (ingestion): korpusu PostgreSQL + pgvector'e yazar.

CSV'deki arıza kayıtlarını okur, açıklamaları embedding'ler ve Fault +
FaultEmbedding tablolarına yazar; ardından pgvector HNSW indeksini kurar.
Bu, üretim retrieval yolunu (retrieval.hybrid_search) besler.

Model boyutu EMBED_DIM ile uyumlu olmalı (Türkçe-adapte için EMBED_DIM=768).

Kullanım:
  EMBED_DIM=768 EMBEDDING_MODEL=adapted DATABASE_URL=... \
    python -m app.services.ingestion --csv ../data/faults_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine, init_db
from app.models import Fault, FaultEmbedding
from app.services.embedding import embed_batch

BATCH = 64


def _to_int(v: str | None) -> int | None:
    v = (v or "").strip()
    return int(v) if v.isdigit() else None


def ingest(csv_path: str | Path, reset: bool = True) -> int:
    """Korpusu DB'ye yükle; eklenen kayıt sayısını döndür."""
    init_db()  # CREATE EXTENSION vector + tablolar
    model_version = get_settings().EMBEDDING_MODEL or "base"

    with open(csv_path, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("description") or "").strip()]

    with SessionLocal() as db:
        if reset:
            db.query(FaultEmbedding).delete()
            db.query(Fault).delete()
            db.commit()

        inserted = 0
        for start in range(0, len(rows), BATCH):
            chunk = rows[start : start + BATCH]
            vectors = embed_batch([r["description"].strip() for r in chunk])
            for r, vec in zip(chunk, vectors):
                fault = Fault(
                    description=r["description"].strip(),
                    category=(r.get("category") or "").strip() or "Bilinmiyor",
                    dtc_code=(r.get("dtc_code") or "").strip() or None,
                    vehicle_model=(r.get("vehicle_model") or "").strip() or None,
                    mileage_km=_to_int(r.get("mileage_km")),
                    solution=(r.get("solution") or "").strip() or "—",
                )
                db.add(fault)
                db.flush()  # fault.id üret
                db.add(FaultEmbedding(
                    fault_id=fault.id, embedding=vec, model_version=model_version,
                ))
                inserted += 1
            db.commit()
            print(f"  {inserted}/{len(rows)} yüklendi...")

    # pgvector HNSW indeksi (cosine) — hızlı yakınsak arama.
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fault_embeddings_hnsw "
            "ON fault_embeddings USING hnsw (embedding vector_cosine_ops)"
        ))
        conn.commit()
    print(f"Tamamlandı: {inserted} kayıt + HNSW indeksi (model: {model_version}).")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Korpusu pgvector'e yükle.")
    default_csv = Path(__file__).resolve().parents[3] / "data" / "faults_dataset.csv"
    parser.add_argument("--csv", default=str(default_csv))
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    ingest(args.csv, reset=not args.no_reset)


if __name__ == "__main__":
    main()
