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
OUT_DIR = ROOT / "models" / "autodiag-embed-tr"
BASE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

SEED = 42
MAX_POS_PER_ANCHOR = 3   # anchor başına pozitif sayısı
MAX_EXAMPLES = 2600      # CPU eğitim süresini sınırla


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


def build_examples():
    """Same-DTC pozitif çiftlerini (augment edilmiş anchor ile) üret."""
    from sentence_transformers import InputExample

    rng = random.Random(SEED)
    by_code: dict[str, list[str]] = defaultdict(list)
    with open(DATASET_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("dtc_code") or "").strip()
            desc = (row.get("description") or "").strip()
            if code and desc:
                by_code[code].append(desc)

    examples = []
    for code, descs in by_code.items():
        if len(descs) < 2:
            continue
        for i, anchor in enumerate(descs):
            others = [d for j, d in enumerate(descs) if j != i]
            rng.shuffle(others)
            for positive in others[:MAX_POS_PER_ANCHOR]:
                # Anchor'ın yarısını argolaştır (terse), yarısını formal bırak.
                a = colloquialize(rng, anchor) if rng.random() < 0.5 else anchor
                examples.append(InputExample(texts=[a, positive]))

    rng.shuffle(examples)
    return examples[:MAX_EXAMPLES]


def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding domain-adaptation.")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    _seed_all()

    from sentence_transformers import SentenceTransformer, losses
    from torch.utils.data import DataLoader

    examples = build_examples()
    print(f"Eğitim çifti: {len(examples)} (kaynak: {DATASET_CSV.name})")
    print(f"Base model: {BASE_MODEL}\n")

    model = SentenceTransformer(BASE_MODEL)
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

    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(OUT_DIR))
    print(f"\nUyarlanmış model kaydedildi: {OUT_DIR}")


if __name__ == "__main__":
    main()
