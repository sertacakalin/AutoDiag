"""Faz İ2 — Gerçek veri içe aktarıcı (Zenodo Automotive Faults, CC-BY 4.0).

Kaynak: Aktc, Obike et al., "Automotive Faults Dataset for Diagnostic and
Maintenance Systems", Zenodo, DOI 10.5281/zenodo.15626055 (CC-BY 4.0).
99 gerçek, yapısal arıza kaydı (İngilizce): kategori, alt-kategori (arızalı
bileşen), semptomlar, teşhis adımları (karar ağacı).

Bu betik kayıtları AutoDiag şemasına çevirir:
  - description     ← semptomlar (arızanın sunumu)
  - solution        ← olası bileşen (alt-kategori) + teşhis adımları özeti
  - category        ← AutoDiag'ın Türkçe kategorisine eşlenir
  - source_category ← orijinal Zenodo kategorisi (çapraz-dilli eval alaka ölçütü)
  - source          ← atıf (CC-BY)

Çıktı: data/real/zenodo_faults.csv

Kullanım:  python scripts/import_zenodo.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_JSON = ROOT / "data" / "real" / "zenodo_automotive_faults.json"
OUT_CSV = ROOT / "data" / "real" / "zenodo_faults.csv"
SOURCE = "Zenodo:10.5281/zenodo.15626055 (CC-BY 4.0)"
DOWNLOAD_URL = (
    "https://zenodo.org/api/records/15626055/files/"
    "automotive_faults_aktc_obike_et_al.json/content"
)


def ensure_source() -> None:
    """Ham JSON yoksa Zenodo'dan indir (tekrarlanabilirlik)."""
    if SRC_JSON.exists():
        return
    import urllib.request

    SRC_JSON.parent.mkdir(parents=True, exist_ok=True)
    print(f"Ham veri indiriliyor: {DOWNLOAD_URL}")
    urllib.request.urlretrieve(DOWNLOAD_URL, SRC_JSON)

# Zenodo kategorisi → AutoDiag Türkçe kategorisi.
CATEGORY_MAP = {
    "Engine Components": "Motor",
    "Engine Compartment": "Motor",
    "Cooling System": "Motor",
    "Fuel System": "Motor",
    "Liquid Systems": "Motor",
    "Electrical System": "Elektrik",
    "Drivetrain": "Şanzıman",
    "Transmission": "Şanzıman",
    "ABS System": "Fren",
    "Emissions System": "Egzoz",
    "Air Conditioning System": "Klima",
    "Wheels & Tires": "Süspansiyon",
    "Steering": "Direksiyon",
}

FIELDS = ["description", "category", "source_category", "subcategory", "solution", "source"]


def summarize_steps(steps: list) -> str:
    """Teşhis adımlarının (karar ağacı) adım adlarını okunur bir özete dönüştür."""
    names = [s.get("step", "").strip() for s in steps if s.get("step")]
    return " → ".join(names[:6])


def main() -> None:
    ensure_source()
    data = json.load(open(SRC_JSON, encoding="utf-8"))
    rows = []
    for e in data:
        symptoms = [s.strip() for s in e.get("symptoms", []) if s.strip()]
        if not symptoms:
            continue
        zen_cat = e.get("category", "").strip()
        subcat = e.get("subcategory", "").strip()
        steps = summarize_steps(e.get("diagnosis_steps", []))
        solution = f"Likely component: {subcat}."
        if steps:
            solution += f" Diagnostic path: {steps}."
        rows.append({
            "description": "; ".join(symptoms),
            "category": CATEGORY_MAP.get(zen_cat, "Motor"),
            "source_category": zen_cat,
            "subcategory": subcat,
            "solution": solution,
            "source": SOURCE,
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"İçe aktarıldı: {len(rows)} gerçek kayıt → {OUT_CSV}")
    cats = sorted({r["source_category"] for r in rows})
    print(f"Zenodo kategorileri ({len(cats)}): {', '.join(cats)}")


if __name__ == "__main__":
    main()
