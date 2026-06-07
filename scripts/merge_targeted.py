"""Hedefli Türkçe veriyi ana korpusa ekler (dedup'lu). Yedek alır."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "data" / "faults_dataset.csv"
TARGETED = ROOT / "data" / "targeted_tr.csv"
BACKUP = ROOT / "data" / "faults_dataset.pre_targeted.csv"
FIELDS = ["description", "category", "dtc_code", "vehicle_model", "mileage_km", "solution"]


def main() -> None:
    shutil.copy(MAIN, BACKUP)
    rows: list[dict] = []
    seen: set[str] = set()
    for path in (MAIN, TARGETED):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                desc = (r.get("description") or "").strip()
                if not desc:
                    continue
                key = desc[:100].lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append({k: r.get(k, "") for k in FIELDS})
    with MAIN.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Birleşik korpus: {len(rows)} kayıt (yedek: {BACKUP.name})")


if __name__ == "__main__":
    main()
