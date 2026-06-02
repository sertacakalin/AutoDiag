"""Şablon-tabanlı sentetik arıza verisi üreticisi (tekrarlanabilir).

Gerçek OBD-II DTC referansından (`data/dtc_reference.csv`) yola çıkarak, her
kod için doğal dilde çeşitlendirilmiş arıza vakaları üretir. Amaç: küçük çekirdek
veriyi (152 kürasyonlu kayıt) gerçekçi varyasyon ve mesafe/araç dağılımıyla
ölçeklemek; retrieval ve reranking değerlendirmesine yeterli sinyal sağlamak.

Metodoloji (tezde anlatılabilir):
  - Belirtiler DTC referansından alınır → şablonlarla cümlelere dönüştürülür.
  - Çözümler, kodun tipik nedenlerinden eylem cümleleri olarak türetilir.
  - Araç/mesafe gerçek Türkiye filo dağılımından örneklenir.
  - random.seed(SEED) ile DETERMİNİSTİK — aynı çıktı her çalıştırmada üretilir.

Çıktı:
  data/faults_generated.csv  — yalnız üretilen kayıtlar
  data/faults_dataset.csv    — çekirdek (seed) + üretilen, birleşik korpus

Kullanım:
  python scripts/generate_dataset.py --per-code 9
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_CSV = ROOT / "data" / "dtc_reference.csv"
SEED_CSV = ROOT / "data" / "faults_seed.csv"
OUT_GENERATED = ROOT / "data" / "faults_generated.csv"
OUT_DATASET = ROOT / "data" / "faults_dataset.csv"

SEED = 42
FIELDS = ["description", "category", "dtc_code", "vehicle_model", "mileage_km", "solution"]

# Türkiye filosundan temsili araçlar.
FLEET = [
    "Renault Megane", "Renault Clio", "Fiat Egea", "Volkswagen Passat",
    "Volkswagen Golf", "Ford Focus", "Opel Astra", "Hyundai i20",
    "Toyota Corolla", "BMW 320i", "Mercedes C180", "Peugeot 301",
    "Dacia Duster", "Honda Civic", "Skoda Octavia", "Renault Symbol",
    "Fiat Doblo", "Citroen C3", "Nissan Qashqai", "Audi A3",
]

# Belirtinin gözlemlendiği bağlam (doğallık için).
CONTEXTS = [
    "soğuk havada ilk çalıştırmada", "hızlanırken", "rölantide",
    "şehir içi trafikte", "yokuş çıkarken", "uzun yol sürüşünde",
    "motor ısındıktan sonra", "vites değiştirirken", "fren yaparken",
    "düşük devirde", "klima açıkken", "rampada kalkışta",
]

# Belirti cümlesi şablonları ({c}=bağlam, {a}/{b}=belirti parçaları).
SENTENCE = [
    "Araç {c} {a} ve {b}.",
    "{c_cap} {a}; ayrıca {b}.",
    "Müşteri {c} {a} ve {b} olduğunu belirtti.",
    "{a_cap}, {b}. Şikayet {c} belirginleşiyor.",
    "{c_cap} {a}, beraberinde {b}.",
    "{a_cap} ve {b} şikayeti mevcut.",
]

# Çözüm eylem fiilleri (nedenden çözüme).
ACTIONS = [
    "değiştirildi", "yenilendi", "temizlendi", "onarıldı",
    "kalibre edildi", "kontrol edilip değiştirildi",
]
SOLUTION = [
    "{x} {act1}.",
    "{x} {act1}; {y} {act2}.",
    "Arıza {x} kaynaklıydı, {act1}. Sonrasında {y} kontrol edildi.",
    "{x} {act1} ve sistem testi yapıldı.",
]

# Mesafe dağılımı (km) — önem derecesine göre kabaca.
MILEAGE_RANGES = {
    "Düşük": (20_000, 140_000),
    "Orta": (40_000, 200_000),
    "Yüksek": (60_000, 260_000),
    "Kritik": (80_000, 300_000),
}


def _lower_first(s: str) -> str:
    # Akronimleri koru (ABS, EGR, O2...): ikinci karakter büyük harf veya rakamsa dokunma.
    if len(s) >= 2 and (s[1].isupper() or s[1].isdigit()):
        return s
    return s[:1].lower() + s[1:] if s else s


def _cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _split(field: str) -> list[str]:
    """';' ile ayrılmış alanı temizlenmiş parçalara böl."""
    return [p.strip() for p in field.split(";") if p.strip()]


def make_description(rng: random.Random, symptoms: list[str]) -> str:
    """Belirti parçalarından doğal bir arıza cümlesi kur."""
    if len(symptoms) >= 2:
        a, b = rng.sample(symptoms, 2)
    elif symptoms:
        a = b = symptoms[0]
    else:
        a = b = "arıza belirtisi"
    ctx = rng.choice(CONTEXTS)
    tpl = rng.choice(SENTENCE)
    return tpl.format(
        c=ctx, c_cap=_cap_first(ctx), a=_lower_first(a), b=_lower_first(b),
        a_cap=_cap_first(a),
    )


def make_solution(rng: random.Random, causes: list[str]) -> str:
    """Tipik nedenlerden bir 'uygulanan çözüm' cümlesi türet."""
    if len(causes) >= 2:
        x, y = rng.sample(causes, 2)
    elif causes:
        x = y = causes[0]
    else:
        x = y = "ilgili parça"
    tpl = rng.choice(SOLUTION)
    return tpl.format(
        x=_cap_first(x), y=_lower_first(y),
        act1=rng.choice(ACTIONS), act2=rng.choice(ACTIONS),
    )


def make_mileage(rng: random.Random, severity: str) -> int:
    """Önem derecesine uygun gerçekçi km değeri (binlik yuvarlama)."""
    lo, hi = MILEAGE_RANGES.get(severity, (40_000, 200_000))
    return round(rng.randint(lo, hi), -3)


def generate(per_code: int) -> list[dict]:
    """Referanstaki her DTC için `per_code` adet vaka üret."""
    rng = random.Random(SEED)
    rows: list[dict] = []
    with open(REF_CSV, encoding="utf-8") as fh:
        ref = list(csv.DictReader(fh))

    for entry in ref:
        symptoms = _split(entry["symptoms_tr"])
        causes = _split(entry["causes_tr"])
        severity = entry["severity"].strip()
        seen: set[str] = set()
        attempts = 0
        produced = 0
        # Aynı kod için tekrarsız açıklamalar üret.
        while produced < per_code and attempts < per_code * 6:
            attempts += 1
            desc = make_description(rng, symptoms)
            if desc in seen:
                continue
            seen.add(desc)
            produced += 1
            rows.append(
                {
                    "description": desc,
                    "category": entry["category"].strip(),
                    "dtc_code": entry["dtc_code"].strip(),
                    "vehicle_model": rng.choice(FLEET),
                    "mileage_km": make_mileage(rng, severity),
                    "solution": make_solution(rng, causes),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_seed() -> list[dict]:
    with open(SEED_CSV, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentetik arıza verisi üreticisi.")
    parser.add_argument("--per-code", type=int, default=9, help="DTC başına vaka sayısı.")
    args = parser.parse_args()

    generated = generate(args.per_code)
    write_csv(OUT_GENERATED, generated)

    seed = read_seed()
    combined = seed + generated
    write_csv(OUT_DATASET, combined)

    cats: dict[str, int] = {}
    for r in combined:
        cats[r["category"]] = cats.get(r["category"], 0) + 1

    print(f"Üretilen: {len(generated)} | Çekirdek: {len(seed)} | Toplam: {len(combined)}")
    print("Kategori dağılımı:")
    for k in sorted(cats):
        print(f"  {k}: {cats[k]}")
    print(f"\nYazıldı:\n  {OUT_GENERATED}\n  {OUT_DATASET}")


if __name__ == "__main__":
    main()
