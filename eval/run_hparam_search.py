"""S7 — Hiperparametre arama (hibrit ağırlık dengesi).

Hibrit skordaki dense/sparse ağırlığını (DENSE_W) bir DOĞRULAMA setinde (gold_set)
tarar, en iyiyi seçer ve HELD-OUT sette (hard_queries) raporlar — sızıntısız
metodoloji. Mevcut varsayılan (0.7/0.3) ile karşılaştırır.

Çalıştırma:  cd eval && python run_hparam_search.py
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

import run_ablation as ab  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_hparam.png")
GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def rank_hybrid_w(idx, query, dense_w):
    sparse_w = 1.0 - dense_w
    final = dense_w * ab._minmax(idx.dense(query)) + sparse_w * ab._minmax(idx.sparse(query))
    return list(np.argsort(-final))


def mean_ndcg(idx, queries, dense_w):
    return float(np.mean([
        ab.ndcg_at_k(rank_hybrid_w(idx, q["query"], dense_w), q["relevant"], 5)
        for q in queries
    ]))


def load(df, path):
    with open(path, encoding="utf-8") as f:
        return ab.build_relevance(df, json.load(f)["queries"])


def main():
    df = pd.read_csv(CORPUS_CSV)
    idx = ab.Index(df["description"].tolist())
    val = load(df, GOLD_PATH)     # doğrulama (tuning)
    test = load(df, HARD_PATH)    # held-out (rapor)

    print(f"Doğrulama (gold): {len(val)} | held-out (hard): {len(test)}\n")
    print(f"{'dense_w':>8}{'val nDCG@5':>14}{'test nDCG@5':>14}")
    print("-" * 36)
    val_scores, test_scores = [], []
    for w in GRID:
        v, t = mean_ndcg(idx, val, w), mean_ndcg(idx, test, w)
        val_scores.append(v); test_scores.append(t)
        print(f"{w:>8.1f}{v:>14.3f}{t:>14.3f}")

    best_i = int(np.argmax(val_scores))
    best_w = GRID[best_i]
    default_v = mean_ndcg(idx, val, 0.7)
    print(f"\nDoğrulamada en iyi: dense_w={best_w} (val {val_scores[best_i]:.3f}, "
          f"test {test_scores[best_i]:.3f})")
    print(f"Mevcut varsayılan dense_w=0.7: val {default_v:.3f}")
    print("Metodoloji: ağırlık YALNIZ doğrulama setinde seçildi; test seti held-out.")

    _plot(val_scores, test_scores, best_w)
    print(f"\nGrafik: {OUT_PNG}")


def _plot(val_scores, test_scores, best_w):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(GRID, val_scores, "o-", label="Doğrulama (gold)")
    ax.plot(GRID, test_scores, "s--", label="Held-out (hard)")
    ax.axvline(best_w, color="gray", ls=":", label=f"en iyi dense_w={best_w}")
    ax.axvline(0.7, color="red", ls=":", alpha=0.5, label="varsayılan 0.7")
    ax.set_xlabel("dense_w (dense ağırlığı; sparse = 1 − dense_w)")
    ax.set_ylabel("nDCG@5")
    ax.set_title("AutoDiag — Hibrit ağırlık taraması (S7 hiperparametre arama)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
