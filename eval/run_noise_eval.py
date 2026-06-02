"""🅲+ — Ses-ayrım değerlendirmesi (hard-negative etkisi).

"Aynı ses farklı sistem" sorgularında (yatak/uğultu/cıyaklama...) modelin doğru
ALT-SİSTEMİ seçip seçmediğini ölçer. Top-1 kategori doğruluğu, base / Türkçe-adapte
/ hard-negative modeller için karşılaştırılır.

Çalıştırma:  cd eval && python run_noise_eval.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from app.services.embedding import normalize_text  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
QUERIES = os.path.join(EVAL_DIR, "noise_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_noise.png")

MODELS = {
    "MiniLM-base": "paraphrase-multilingual-MiniLM-L12-v2",
    "TR-trmteb-adapte": os.path.join(ROOT_DIR, "models", "autodiag-embed-tr-trmteb"),
    "TR-adapte-HN": os.path.join(ROOT_DIR, "models", "autodiag-embed-tr-hn"),
}


def main():
    from sentence_transformers import SentenceTransformer

    df = pd.read_csv(CORPUS_CSV)
    descs = df["description"].tolist()
    cats = df["category"].tolist()
    with open(QUERIES, encoding="utf-8") as f:
        queries = json.load(f)["queries"]
    print(f"Korpus: {len(descs)} | ses sorgusu: {len(queries)}\n")

    results = {}
    for name, ref in MODELS.items():
        if os.path.isabs(ref) and not os.path.isdir(ref):
            print(f"ATLA {name}: yerel model yok")
            continue
        model = SentenceTransformer(ref)
        docv = np.array(model.encode([normalize_text(d) for d in descs],
                                     normalize_embeddings=True))
        correct, top3 = 0, 0
        details = []
        for item in queries:
            q = np.array(model.encode([normalize_text(item["query"])],
                                      normalize_embeddings=True)[0])
            order = np.argsort(-(docv @ q))
            top_cat = cats[order[0]]
            top3_cats = [cats[order[i]] for i in range(3)]
            ok = top_cat == item["category"]
            correct += ok
            top3 += item["category"] in top3_cats
            details.append((item["query"][:34], item["category"], top_cat, ok))
        acc1 = correct / len(queries)
        acc3 = top3 / len(queries)
        results[name] = (acc1, acc3)
        print(f"=== {name}: Top-1 kategori doğruluğu {acc1:.2f} | Top-3 {acc3:.2f} ===")
        for q, exp, got, ok in details:
            print(f"  {'✓' if ok else '✗'} {q:<36} bek:{exp:<11} → {got}")
        print()

    _plot(results)
    print(f"Grafik: {OUT_PNG}")


def _plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(results.keys())
    x = np.arange(len(names))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8.5, 5))
    a1 = ax.bar(x - w/2, [results[n][0] for n in names], w, label="Top-1 kategori")
    a3 = ax.bar(x + w/2, [results[n][1] for n in names], w, label="Top-3 kategori")
    ax.bar_label(a1, fmt="%.2f", fontsize=8); ax.bar_label(a3, fmt="%.2f", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=9)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Doğruluk")
    ax.set_title("AutoDiag — Ses-ayrım doğruluğu (hard-negative eğitim etkisi)")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
