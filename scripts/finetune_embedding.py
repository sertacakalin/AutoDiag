"""Embedding domain-adaptation: çok dilli MiniLM'i Türkçe otomotiv arıza
alanına uyarlar (contrastive / MultipleNegativesRankingLoss).

Gerekçe: Ablation, argo/günlük girdi ile formal kayıt arasında bir alan farkı
(domain gap) ölçtü. Sorgu genişletme (QN) bu farkı çıkarım anında kapatıyor;
burada ek olarak EĞİTİM zamanında embedding uzayını alana uyarlıyoruz —
aynı kök-nedenli (aynı DTC kodu) vakaları birbirine yaklaştırarak.

Eğitim sinyali (sızıntısız):
  - Pozitif çiftler: AYNI DTC koduna sahip iki vaka açıklaması.
  - Anchor augmentasyonu: JENERİK token-dropout + küçük harf (terse/gürültülü
    kullanıcı girdisini taklit eder). Test setindeki (hard_queries) argo kelime
    haritası ENJEKTE EDİLMEZ → değerlendirme held-out kalır.
  - In-batch negatifler: MNRL, batch'teki diğer pozitifleri negatif sayar.

Test sorguları (gold_set, hard_queries) eğitimde HİÇ kullanılmaz.

Kullanım:
  python scripts/finetune_embedding.py --epochs 2 --batch 32
Çıktı: models/autodiag-embed-tr/ (uyarlanmış model)
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_CSV = ROOT / "data" / "faults_dataset.csv"
DEFAULT_OUT = ROOT / "models" / "autodiag-embed-tr"
DEFAULT_BASE = "paraphrase-multilingual-MiniLM-L12-v2"

SEED = 42
MAX_POS_PER_ANCHOR = 3   # anchor başına pozitif sayısı
MAX_EXAMPLES = 2600      # CPU eğitim süresini sınırla
HARD_NEG_PROB = 0.4      # ankorların oranı kadar hard-negative ekle (takası dengele)


def _seed_all() -> None:
    import torch

    random.seed(SEED)
    torch.manual_seed(SEED)


def colloquialize(rng: random.Random, text: str) -> str:
    """Jenerik gürültü: küçük harf + rastgele token düşürme (anlam korunur).

    Test setine özgü argo SÖZLÜĞÜ kullanılmaz — bu kasıtlı; amaç genel
    terse/gürültülü girdiye dayanıklılık, sızıntısız.
    """
    tokens = text.lower().split()
    if len(tokens) > 4:
        drop = rng.randint(1, 2)
        for _ in range(drop):
            if len(tokens) > 3:
                tokens.pop(rng.randrange(len(tokens)))
    return " ".join(tokens)


def _tokens(text: str) -> set[str]:
    """Ayırt edici içerik kelimeleri (uzunluk ≥ 4)."""
    import re

    low = re.sub(r"\s+", " ", text.lower()).strip()
    return {t for t in low.split() if len(t) >= 4}


def mine_hard_negative(rng, anchor_tokens, anchor_cat, pool, k=60):
    """Anchor ile FARKLI kategoride, metinsel en benzer örneği bul (hard negative).

    'Aynı ses farklı sistem' (motor yatağı ≠ amortisör) ayrımını öğretir.
    """
    candidates = rng.sample(pool, min(k, len(pool)))
    best, best_ov = None, 0
    for desc, cat, toks in candidates:
        if cat == anchor_cat:
            continue
        ov = len(anchor_tokens & toks)
        if ov > best_ov:
            best, best_ov = desc, ov
    return best if best_ov >= 1 else None


def build_examples():
    """Same-grup pozitif çiftleri + cross-kategori HARD NEGATIVE üçlüleri.

    Gruplama: dtc_code varsa onunla, yoksa (mekanik/ses arızaları) kategoriyle.
    """
    from sentence_transformers import InputExample

    rng = random.Random(SEED)
    by_group: dict[str, list[str]] = defaultdict(list)
    pool: list[tuple] = []  # (desc, category, tokenset) — negatif madenciliği için
    with open(DATASET_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            desc = (row.get("description") or "").strip()
            cat = (row.get("category") or "").strip()
            if not desc:
                continue
            code = (row.get("dtc_code") or "").strip()
            group = code or f"cat:{cat}"  # DTC yoksa kategoriye göre grupla
            by_group[group].append(desc)
            pool.append((desc, cat, _tokens(desc)))

    desc_cat = {d: c for d, c, _ in pool}
    examples = []
    for group, descs in by_group.items():
        if len(descs) < 2:
            continue
        for i, anchor in enumerate(descs):
            others = [d for j, d in enumerate(descs) if j != i]
            rng.shuffle(others)
            anchor_cat = desc_cat.get(anchor, "")
            for positive in others[:MAX_POS_PER_ANCHOR]:
                # Anchor'ın yarısını argolaştır (terse), yarısını formal bırak.
                a = colloquialize(rng, anchor) if rng.random() < 0.5 else anchor
                neg = (
                    mine_hard_negative(rng, _tokens(anchor), anchor_cat, pool)
                    if rng.random() < HARD_NEG_PROB
                    else None
                )
                if neg:
                    examples.append(InputExample(texts=[a, positive, neg]))
                else:
                    examples.append(InputExample(texts=[a, positive]))

    rng.shuffle(examples)
    return examples[:MAX_EXAMPLES]


def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding domain-adaptation.")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--base-model", default=DEFAULT_BASE, help="Base model id/yol.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Çıktı klasörü.")
    args = parser.parse_args()

    _seed_all()

    from sentence_transformers import SentenceTransformer, losses
    from torch.utils.data import DataLoader

    examples = build_examples()
    print(f"Eğitim çifti: {len(examples)} (kaynak: {DATASET_CSV.name})")
    print(f"Base model: {args.base_model}\n")

    model = SentenceTransformer(args.base_model)
    loader = DataLoader(examples, shuffle=True, batch_size=args.batch)
    loss = losses.MultipleNegativesRankingLoss(model)
    warmup = int(len(loader) * args.epochs * 0.1)

    print(f"Eğitiliyor: {args.epochs} epoch × {len(loader)} adım (warmup={warmup})...")
    model.fit(
        train_objectives=[(loader, loss)],
        epochs=args.epochs,
        warmup_steps=warmup,
        show_progress_bar=True,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out))
    print(f"\nUyarlanmış model kaydedildi: {out}")


if __name__ == "__main__":
    main()
