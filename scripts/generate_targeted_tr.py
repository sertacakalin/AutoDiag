"""Hedefli Türkçe veri üretimi (Ollama, ücretsiz yerel LLM).

Korpustaki ZAYIF alanları (süspansiyon/direksiyon/mekanik ses arızaları —
"ön takım", rotbaşı, rotil, salıncak, z rot, rulman vb.) doldurur. Yaklaşım
GROUNDED: kategori + çözüm + bileşen SABİT (uydurma yok); Ollama yalnız belirtinin
çeşitli, gerçekçi, günlük-dil Türkçe ifadelerini üretir. Böylece embedding bu
arıza tiplerini ve argoyu daha iyi öğrenir, retrieval daha çok örnekle eşleşir.

Rastgele İngilizce veri (NHTSA) Türkçe-argo performansını seyreltmişti
(eval/run_data_compare.py); bu farklı: Türkçe + hedefli + kapsama boşluğunu kapatır.

Kullanım:
    python scripts/generate_targeted_tr.py --per-template 15 --out data/targeted_tr.csv
Ön koşul: Ollama açık (http://localhost:11434), model aya-expanse:8b.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "aya-expanse:8b"
SEED = 42

# Türkiye pazarı araçları + km aralığı (gerçekçi meta).
VEHICLES = [
    "Renault Megane", "Renault Clio", "Fiat Egea", "Volkswagen Golf",
    "Volkswagen Passat", "Ford Focus", "Opel Astra", "Toyota Corolla",
    "Hyundai i20", "Hyundai Accent", "Dacia Duster", "Peugeot 301",
    "Honda Civic", "Skoda Octavia", "Citroen C-Elysee", "Nissan Qashqai",
]

# GROUNDED arıza şablonları — gerçek bileşen/belirti/çözüm. Ollama yalnız
# 'hint'i çeşitli Türkçe ifadelerle yeniden yazar; kategori/çözüm sabit.
# 'anchors': üretilen ifade EN AZ birini içermeli; konudan kaçan (off-topic)
# halüsinasyonlar elenir (garbage-in koruması).
TEMPLATES = [
    {"category": "Direksiyon", "component": "rotbaşı aşınması",
     "hint": "ön taraftan/rotbaşından tıkırtı, viraj alırken ve kasis geçerken ses, direksiyonda boşluk",
     "solution": "Rotbaşları aşınmıştı, sağ-sol rotbaşı değişti ve ön düzen ayarı yapıldı.",
     "anchors": ["rotbaş", "ön takım", "ön taraf", "viraj", "kasis", "direksiyon", "tık", "takırt"]},
    {"category": "Süspansiyon", "component": "rotil (rot mafsalı) boşluğu",
     "hint": "ön takımdan tık tık ses, bozuk yolda takırtı, tekerlekte oynama hissi",
     "solution": "Rotil boşluk yapmıştı, alt rotiller değişti.",
     "anchors": ["rotil", "ön takım", "ön taraf", "bozuk yol", "takırt", "tık", "oynama"]},
    {"category": "Süspansiyon", "component": "salıncak burcu aşınması",
     "hint": "ön taraftan gümbürtü/takırtı, fren yaparken öne dalma, kasiste ses",
     "solution": "Salıncak burçları aşınmıştı, salıncak takımı ve burçlar yenilendi.",
     "anchors": ["salıncak", "burç", "ön taraf", "ön takım", "gümbür", "takırt", "kasis"]},
    {"category": "Süspansiyon", "component": "amortisör zayıflaması",
     "hint": "araç zıp zıp yapıyor, dalgalı yolda yaylanma, kasiste küt sesi, yol tutuşu bozuk",
     "solution": "Ön amortisörler zayıflamıştı, amortisör takımı değişti.",
     "anchors": ["amortis", "zıp", "yaylan", "kasis", "dalga", "yol tut", "küt", "sek"]},
    {"category": "Süspansiyon", "component": "z rot (viraj demiri linki)",
     "hint": "kasis ve bozuk yolda ön taraftan takırtı, hızlı yolda zınk zınk ses",
     "solution": "Z rotlar (viraj demiri bağlantıları) boşluk yapmıştı, değişti.",
     "anchors": ["z rot", "viraj demir", "kasis", "ön takım", "ön taraf", "takırt", "zınk", "bozuk yol"]},
    {"category": "Süspansiyon", "component": "denge çubuğu burcu",
     "hint": "düşük hızda kasiste takırtı, ön takımda kuru ses, stabilizatör sesi",
     "solution": "Denge çubuğu (stabilizatör) burçları sertleşmişti, burçlar değişti.",
     "anchors": ["denge çubuğu", "stabiliz", "kasis", "ön takım", "ön taraf", "takırt", "kuru ses"]},
    {"category": "Süspansiyon", "component": "tekerlek rulmanı",
     "hint": "hızla artan uğultu/vınlama, belli hızda uçak sesi gibi uğultu, viraja girince ses değişiyor",
     "solution": "Ön tekerlek rulmanı ses yapıyordu, rulman ve poyra değişti.",
     "anchors": ["uğultu", "uğul", "vınla", "uçak", "rulman", "tekerlek", "teker", "hız"]},
    {"category": "Direksiyon", "component": "aks (homokinetik mafsal)",
     "hint": "direksiyon kırıp dönerken tak tak ses, manevrada tıkırtı, viraj dönüşünde takırtı",
     "solution": "Aks kafası (homokinetik mafsal) aşınmıştı, aks komple değişti.",
     "anchors": ["aks", "mafsal", "direksiyon", "viraj", "manevra", "dönerken", "tak tak", "tıkırt"]},
    {"category": "Motor", "component": "motor takozu",
     "hint": "rölantide titreşim ve gümbürtü, vites takarken küt sesi, gaz kesince sarsıntı",
     "solution": "Motor takozu çökmüştü, takoz değişti, titreşim kayboldu.",
     "anchors": ["takoz", "rölanti", "titreşim", "titre", "vites tak", "gümbür", "sarsınt", "gaz kes"]},
    {"category": "Motor", "component": "triger/aksesuar kayışı",
     "hint": "motordan cıyak/gıcırtı sesi, soğukta ıslık gibi ses, devirle artan gıcırtı",
     "solution": "Aksesuar (V) kayışı gevşemiş/çatlamıştı, kayış ve gergi rulmanı değişti.",
     "anchors": ["kayış", "gıcırt", "cıyak", "ıslık", "devir", "soğuk", "motor"]},
    {"category": "Süspansiyon", "component": "helezon yay (kırık)",
     "hint": "ön taraf bir köşeden çökük, kasiste metalik takırtı, direksiyonda titreme",
     "solution": "Ön helezon yay kırılmıştı, yay değişti.",
     "anchors": ["yay", "helezon", "çökük", "çökme", "kasis", "ön taraf", "takırt", "titre"]},
    {"category": "Direksiyon", "component": "kremayer (direksiyon kutusu)",
     "hint": "direksiyonda boşluk ve takırtı, ortada oynama, viraj sonrası ses",
     "solution": "Direksiyon kutusu (kremayer) boşluk yapmıştı, revizyon yapıldı.",
     "anchors": ["direksiyon", "boşluk", "kremayer", "kutu", "takırt", "oynama", "viraj"]},
    {"category": "Şanzıman", "component": "debriyaj/baskı bilyası",
     "hint": "debriyaja basınca cıyak ses, vites geçişinde zorlanma, pedala basınca uğultu",
     "solution": "Debriyaj baskı bilyası ses yapıyordu, debriyaj seti değişti.",
     "anchors": ["debriyaj", "vites", "pedal", "cıyak", "uğultu", "baskı", "kavrama"]},
    {"category": "Egzoz", "component": "egzoz askısı/flex boru",
     "hint": "alttan tıkırtı, rölantide vızıltı, kasiste egzoz çarpma sesi, patlama benzeri ses",
     "solution": "Egzoz flex borusu çatlamış, askı lastiği kopmuştu; flex ve askı yenilendi.",
     "anchors": ["egzoz", "alttan", "tıkırt", "vızıl", "kasis", "patlama", "flex", "askı"]},
    {"category": "Motor", "component": "alternatör/gergi rulmanı",
     "hint": "motordan vınlama/uğultu, soğukta gıcırtı, devirle değişen ses",
     "solution": "Alternatör rulmanı/gergi rulmanı aşınmıştı, rulman değişti.",
     "anchors": ["vınla", "uğultu", "gıcırt", "motor", "devir", "soğuk", "rulman", "alternatör"]},
    {"category": "Fren", "component": "balata aşınma fişeği/disk",
     "hint": "fren yaparken cıyak/gıcırtı, frende titreme, metalik sürtme sesi",
     "solution": "Balatalar bitmiş, disklerde aşınma vardı; balata ve disk değişti.",
     "anchors": ["fren", "cıyak", "gıcırt", "titre", "sürtme", "balata", "disk", "metalik"]},
    # --- İterasyon 1: Hedefli boşluk doldurma ---
    # Motor güç kaybı / boğulma (turbo, EGR, enjektör, emme manifoldu sızıntısı)
    # Gerçek nedenler: EGR valfi kurumlanması (CO/NOx oranını bozarak güç kaybı),
    # turbo/intercooler sızıntısı (şarj basıncı düşer), enjektör tıkanması (püskürtme
    # profili bozulur), emme manifoldu contası sızıntısı (yalancı hava → yalın karışım →
    # güç kaybı). DTC aralığı: P0087-P0093, P0171, P0299, P2015 vb.
    {"category": "Motor", "component": "motor güç kaybı / boğulma (EGR/turbo/enjektör)",
     "hint": "şehir içinde gaz pedalına basınca motor güç vermiyor sanki boğuluyor, yokuşta zorlanıyor, "
             "devir çıkıyor ama hız artmıyor, ivmelenme yavaş, gaz tepkisi azaldı",
     "solution": "EGR valfi kurum tutmuş, intercooler hortumu gevşemiş; EGR temizlendi, hortum "
                 "sıkıldı, güç ve ivmelenme normale döndü.",
     "anchors": ["güç", "boğul", "çekmiyor", "zorlan", "devir", "ivme", "yavaş", "pedal", "motor"]},
    # Süspansiyon seviye sensörü / xenon far otomatik yükseklik ayarı
    # Gerçek mekanizma: Xenon/LED-matrix farları otomatik yükseklik ayarı (auto-leveling)
    # için süspansiyon yükseklik potansiyometre sensöründen (HLLS) sinyal alır. Sensör
    # veya bağlantı arızasında far yönü sabitlenir ve "far seviyesi ayarlanmıyor" hatası +
    # C1413 / C1531 benzeri DTC üretilir. VW Passat/Golf xenon, Renault Laguna/Vel Satis
    # adaptive headlights, Opel Insignia AFL sistemleri bu sensörü kullanır.
    {"category": "Süspansiyon", "component": "süspansiyon yükseklik sensörü / far-leveling",
     "hint": "far seviyesi otomatik ayarlanmıyor panelde uyarı çıktı, araç yüklüyken far yukarı "
             "kalıyor manuel ayar yapmak gerekiyor, sürüş yüksekliği sensörü arıza kodu var",
     "solution": "Ön sol süspansiyon yükseklik sensörü (seviye potansiyometre) arızalanmıştı; "
                 "sensör değiştirildi, far otomatik seviyeleme düzeldi.",
     "anchors": ["far", "seviye", "sensör", "yüksekl", "ayarlanm", "süspansiyon", "leveling", "uyarı"]},
]


def _relevant(text: str, anchors: list[str]) -> bool:
    """İfade en az bir anchor içeriyor mu (konu dışı halüsinasyonu eler)."""
    low = text.lower()
    return any(a in low for a in anchors)


# Gevezelik/yorum/soru işaretleri — servis kaydı dilinde olmaması gereken üslup.
_CHATTY = (
    "?", "lazım", "sanırım", "acaba", "endişe", "merak", "galiba", "umarım",
    "bilir misin", "ruhu", "selam", "düşünmeli", "düşünüyorum", "korkar",
    "tavsiye", "ne yapmalı", "herhalde", "diye düşün", "yardım", "mı düşün",
    "mu düşün", "derdi", "sorarsan", "bence", "keşke",
)


# 16 şablonun HİÇBİRİNİN konusu olmayan bileşenler — geçerse off-topic kaçaktır.
_OFF_TOPIC = ("koltuk", "cam ", "camlar", "far ", "farlar", "klima",
              "radyo", "ayna", "silecek", "kapı kol", "torpido")


def _clean_style(text: str) -> bool:
    """Servis-kaydı üslubu mu? Geveze/soru/yorum/uzun/off-topic ifadeleri eler."""
    low = text.lower()
    if len(text) > 130:  # servis notu kısadır
        return False
    if any(o in low for o in _OFF_TOPIC):
        return False
    return not any(m in low for m in _CHATTY)


def ollama_phrasings(hint: str, n: int, retries: int = 2) -> list[str]:
    """Ollama'dan belirti için n adet çeşitli Türkçe ifade üret (JSON dizi)."""
    prompt = (
        "Bir oto servisinin arıza kayıt defterine yazılan kısa belirti notları "
        "üreteceksin. Müşterinin şikayetini USTANIN deftere yazdığı gibi, KISA ve "
        "NESNEL bir cümleyle anlat.\n\n"
        f"Belirti: {hint}\n\n"
        f"{n} ADET farklı, tek cümlelik, gerçekçi Türkçe belirti notu üret. "
        "Günlük teknik dil kullan ('ön takımdan tıkırtı', 'kasiste takırtı'). "
        "YASAK: soru sorma (? kullanma), duygu/yorum yazma "
        "('endişelendirici', 'dikkatli olmalı', 'sanırım', 'acaba', 'merak', "
        "'galiba', 'umarım' gibi), benzetme/şiir yapma ('ruhu var' gibi), "
        "kişiye hitap etme ('bilir misin'). SADECE belirti.\n"
        "BAŞKA bir arıza/sistem (yağ, klima, far, cam, koltuk) EKLEME.\n\n"
        'SADECE şu JSON: {"ifadeler": ["...", "...", ...]}'
    )
    payload = json.dumps({
        "model": OLLAMA_MODEL, "prompt": prompt,
        "stream": False, "format": "json", "options": {"temperature": 0.5},
    }).encode("utf-8")
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                inner = json.loads(data.get("response", "{}"))
                items = inner.get("ifadeler") or inner.get("phrasings") or []
                cleaned = [str(s).strip() for s in items if str(s).strip()]
                if cleaned:
                    return cleaned[:n]
        except Exception as e:  # ağ/parse/timeout — defensive
            if attempt == retries:
                print(f"  ! üretim hatası ({hint[:30]}...): {e}", file=sys.stderr)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Hedefli Türkçe veri üretimi (Ollama).")
    parser.add_argument("--per-template", type=int, default=15)
    parser.add_argument("--out", default="data/targeted_tr.csv")
    args = parser.parse_args()

    rng = random.Random(SEED)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    seen: set[str] = set()
    for i, t in enumerate(TEMPLATES, 1):
        print(f"[{i}/{len(TEMPLATES)}] {t['component']} ({t['category']}) ...", flush=True)
        # İki filtre (konu + üslup) eleyeceği için fazladan iste.
        raw = ollama_phrasings(t["hint"], args.per_template + 14)
        kept = 0
        for desc in raw:
            if kept >= args.per_template:
                break
            key = desc[:80].lower()
            # Konu dışı (anchor yok), gevezelik/yorum (üslup), kısa/yinelenen ele.
            if (len(desc) < 15 or key in seen
                    or not _relevant(desc, t["anchors"])
                    or not _clean_style(desc)):
                continue
            seen.add(key)
            rows.append({
                "description": desc,
                "category": t["category"],
                "dtc_code": "",
                "vehicle_model": rng.choice(VEHICLES),
                "mileage_km": rng.randint(60, 280) * 1000,
                "solution": t["solution"],
            })
            kept += 1
        print(f"     +{kept}/{len(raw)} ifade tutuldu (toplam {len(rows)})", flush=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "description", "category", "dtc_code", "vehicle_model", "mileage_km", "solution"])
        w.writeheader()
        w.writerows(rows)

    import collections
    cats = collections.Counter(r["category"] for r in rows)
    print(f"\n✓ {len(rows)} hedefli Türkçe kayıt → {out_path}")
    for c, n in cats.most_common():
        print(f"  {n:4}  {c}")


if __name__ == "__main__":
    main()
