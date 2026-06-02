"""S6 — İstatistiksel anlamlılık (bootstrap güven aralıkları + permütasyon testi).

Ablation iddialarını istatistiksel olarak temellendirir: yöntemlerin nDCG@5
ortalamaları için %95 bootstrap güven aralığı, ve yöntem çiftleri arasındaki
farkın eşli (paired) bootstrap ile anlamlılığı (p-değeri).

Karşılaştırılan iddialar:
  - Standart: Hibrit vs BM25 (hibrit gerçekten üstün mü?)
  - Zorlu:    Hibrit+Rerank vs Hibrit (rerank kazancı anlamlı mı?)

Çalıştırma:  cd eval && python run_significance.py
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
N_BOOT = 10000
RNG = np.random.default_rng(42)


def per_query_ndcg(rank_fn, idx, queries) -> np.ndarray:
    """Her sorgu için nDCG@5 (bootstrap için sorgu-düzeyi skorlar)."""
    return np.array([
        ab.ndcg_at_k(rank_fn(idx, q["query"]), q["relevant"], 5) for q in queries
    ])


def ci(values: np.ndarray, n=N_BOOT) -> tuple[float, float, float]:
    """Ortalama + %95 bootstrap güven aralığı."""
    means = np.array([
        RNG.choice(values, size=len(values), replace=True).mean() for _ in range(n)
    ])
    return float(values.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_test(a: np.ndarray, b: np.ndarray, n=N_BOOT) -> tuple[float, float, float, float]:
    """Eşli bootstrap: fark (a−b) ortalaması, %95 GA ve iki-yönlü p-değeri."""
    diff = a - b
    boot = np.array([
        diff[RNG.integers(0, len(diff), len(diff))].mean() for _ in range(n)
    ])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    # İki yönlü p: sıfır farkın bootstrap dağılımındaki konumu.
    p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())
    return float(diff.mean()), float(lo), float(hi), float(min(p, 1.0))


def load(df, path):
    with open(path, encoding="utf-8") as f:
        return ab.build_relevance(df, json.load(f)["queries"])


def main():
    df = pd.read_csv(CORPUS_CSV)
    descriptions = df["description"].tolist()
    print(f"Korpus: {len(descriptions)} | bootstrap iterasyon: {N_BOOT}")
    idx = ab.Index(descriptions)
    std_q = load(df, GOLD_PATH)
    hard_q = load(df, HARD_PATH)

    cases = [
        ("Standart", std_q, "Hibrit", ab.rank_hybrid, "BM25", ab.rank_bm25),
        ("Zorlu", hard_q, "Hibrit+Rerank", ab.rank_hybrid_rerank, "Hibrit", ab.rank_hybrid),
    ]

    for setname, q, name_a, fn_a, name_b, fn_b in cases:
        a = per_query_ndcg(fn_a, idx, q)
        b = per_query_ndcg(fn_b, idx, q)
        ma, la, ha = ci(a)
        mb, lb, hb = ci(b)
        d, dlo, dhi, p = paired_test(a, b)
        sig = "ANLAMLI" if (dlo > 0 or dhi < 0) else "anlamlı değil"
        print(f"\n=== {setname} (nDCG@5, n={len(q)} sorgu) ===")
        print(f"  {name_a:<16} {ma:.3f}  [%95 GA: {la:.3f}–{ha:.3f}]")
        print(f"  {name_b:<16} {mb:.3f}  [%95 GA: {lb:.3f}–{hb:.3f}]")
        print(f"  Fark ({name_a}−{name_b}): {d:+.3f}  [%95 GA: {dlo:+.3f}–{dhi:+.3f}]  "
              f"p≈{p:.3f}  → {sig}")

    print("\nNot: Küçük sorgu setlerinde (n=10–24) güven aralıkları geniştir; "
          "büyük gerçek-veri setiyle daralır (gelecek iş).")


if __name__ == "__main__":
    main()
