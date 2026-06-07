"""NHTSA ODI Complaints → AutoDiag korpus şeması (gerçek veri katmanı).

NHTSA complaints API'sinden (ABD kamu malı) gerçek sürücü arıza şikayetlerini
çeker, projenin 8 kategorisine eşler, şemaya dönüştürür:
    description, category, dtc_code, vehicle_model, mileage_km, solution

- Scraping YOK: resmi JSON API (api.nhtsa.gov/complaints/complaintsByVehicle).
- Rate-limit: istekler arası bekleme (siteyi yormamak için).
- Yalnız 8 kategorimize eşlenen şikayetler tutulur; alakasızlar (airbag,
  emniyet kemeri, yapı vb.) elenir.
- 'solution' ve 'dtc_code' NHTSA'da yoktur → boş bırakılır (retrieval için
  description yeterli; embedding eğitimi kategori bazlı gruplar).

Kullanım:
    python scripts/import_nhtsa.py --out data/real/nhtsa_faults.csv --per-vehicle 120
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.nhtsa.gov/complaints/complaintsByVehicle"

# NHTSA component → AutoDiag kategori eşlemesi. Çok-bileşenli stringlerde
# (ör. "ELECTRICAL SYSTEM,UNKNOWN OR OTHER") ilk eşleşen kazanır.
CATEGORY_MAP: dict[str, str] = {
    "ENGINE": "Motor",
    "ENGINE AND ENGINE COOLING": "Motor",
    "FUEL/PROPULSION SYSTEM": "Motor",
    "FUEL SYSTEM, GASOLINE": "Motor",
    "VEHICLE SPEED CONTROL": "Motor",
    "SERVICE BRAKES": "Fren",
    "SERVICE BRAKES, HYDRAULIC": "Fren",
    "POWER TRAIN": "Şanzıman",
    "ELECTRICAL SYSTEM": "Elektrik",
    "EXTERIOR LIGHTING": "Elektrik",
    "SUSPENSION": "Süspansiyon",
    "WHEELS": "Süspansiyon",
    "TIRES": "Süspansiyon",
    "STEERING": "Direksiyon",
    "EXHAUST SYSTEM": "Egzoz",
    "AIR CONDITIONER": "Klima",
    "EQUIPMENT": "Klima",
}

# ABD pazarında bol şikayeti olan araçlar (kategori çeşitliliği için geniş seçim).
VEHICLES: list[tuple[str, str, int]] = [
    ("honda", "accord", 2017), ("honda", "civic", 2016), ("honda", "cr-v", 2018),
    ("toyota", "camry", 2018), ("toyota", "corolla", 2017), ("toyota", "rav4", 2019),
    ("ford", "f-150", 2016), ("ford", "focus", 2015), ("ford", "escape", 2017),
    ("ford", "fusion", 2014), ("chevrolet", "silverado", 2016), ("chevrolet", "malibu", 2016),
    ("chevrolet", "equinox", 2018), ("nissan", "altima", 2016), ("nissan", "rogue", 2017),
    ("nissan", "sentra", 2018), ("jeep", "grand-cherokee", 2015), ("jeep", "wrangler", 2018),
    ("hyundai", "sonata", 2015), ("hyundai", "elantra", 2017), ("hyundai", "santa-fe", 2019),
    ("kia", "optima", 2016), ("kia", "sorento", 2016), ("volkswagen", "jetta", 2015),
    ("volkswagen", "passat", 2016), ("subaru", "outback", 2017), ("subaru", "forester", 2018),
    ("dodge", "ram-1500", 2014), ("gmc", "sierra", 2016), ("mazda", "cx-5", 2017),
    ("chrysler", "pacifica", 2017), ("ram", "1500", 2019), ("bmw", "3-series", 2014),
    ("mercedes-benz", "c-class", 2015), ("audi", "a4", 2016), ("tesla", "model-3", 2019),
]


def fetch(make: str, model: str, year: int, retries: int = 3) -> list[dict]:
    """Bir araç için şikayetleri çek. Hata/timeout'ta retry; başarısızsa []."""
    qs = urllib.parse.urlencode({"make": make, "model": model, "modelYear": year})
    url = f"{API}?{qs}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AutoDiag-academic/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                import json
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", []) or []
        except Exception as e:  # ağ/JSON/timeout — defensive
            if attempt == retries - 1:
                print(f"  ! {make} {model} {year} alınamadı: {e}", file=sys.stderr)
                return []
            time.sleep(2 * (attempt + 1))
    return []


def map_category(components: str) -> str | None:
    """Component string'ini 8 kategoriden birine eşle; eşleşme yoksa None."""
    if not components:
        return None
    for token in components.split(","):
        cat = CATEGORY_MAP.get(token.strip().upper())
        if cat:
            return cat
    return None


def clean_summary(text: str) -> str:
    """Şikayet metnini sadeleştir: fazla boşluk, baştaki şablon ifadeyi koru."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="NHTSA gerçek şikayet verisini içe aktar.")
    parser.add_argument("--out", default="data/real/nhtsa_faults.csv")
    parser.add_argument("--per-vehicle", type=int, default=120,
                        help="Araç başına en fazla kayıt (çeşitlilik için).")
    parser.add_argument("--min-len", type=int, default=60,
                        help="Bu uzunluğun altındaki açıklamalar elenir.")
    parser.add_argument("--delay", type=float, default=0.6,
                        help="İstekler arası bekleme (saniye) — rate limit.")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    seen: set[str] = set()
    cat_counts: dict[str, int] = {}

    for i, (make, model, year) in enumerate(VEHICLES, 1):
        print(f"[{i}/{len(VEHICLES)}] {make} {model} {year} ...", flush=True)
        results = fetch(make, model, year)
        kept = 0
        for r in results:
            if kept >= args.per_vehicle:
                break
            category = map_category(r.get("components", ""))
            if not category:
                continue
            desc = clean_summary(r.get("summary", ""))
            if len(desc) < args.min_len:
                continue
            key = desc[:120].lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "description": desc,
                "category": category,
                "dtc_code": "",
                "vehicle_model": f"{make.title()} {model.replace('-', ' ').title()} {year}",
                "mileage_km": "",
                "solution": "",  # NHTSA şikayetlerinde onarım bilgisi yok
            })
            cat_counts[category] = cat_counts.get(category, 0) + 1
            kept += 1
        print(f"     +{kept} kayıt (toplam {len(rows)})", flush=True)
        time.sleep(args.delay)  # rate limit

    # Yaz
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "description", "category", "dtc_code", "vehicle_model", "mileage_km", "solution",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ {len(rows)} gerçek NHTSA kaydı → {out_path}")
    print("Kategori dağılımı:")
    for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {n:5}  {cat}")


if __name__ == "__main__":
    main()
