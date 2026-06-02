"""Offline değerlendirme: TF-IDF vs Dense vs Hibrit arama karşılaştırması.

Veritabanı GEREKTİRMEZ. Vektörler bellek içinde üretilir. faults_seed.csv ve
gold_set.json kullanılarak precision@k, recall@k ve MRR hesaplanır; sonuç tablo
olarak yazdırılır ve eval/results.png çubuk grafiği üretilir.

Çalıştırma:  cd eval && python run_eval.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# backend'i import yoluna ekle (embedding servisini paylaşmak için).
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from app.services.embedding import embed_batch, normalize_text  # noqa: E402

CSV_PATH = os.path.join(ROOT_DIR, "data", "faults_seed.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
RESULTS_PNG = os.path.join(EVAL_DIR, "results.png")


# ----------------------------- Metrikler -----------------------------
def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    top = ranked[:k]
    if not top:
        return 0.0
    return sum(1 for d in top if d in relevant) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = ranked[:k]
    return sum(1 for d in top if d in relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """İlk alakalı sonucun sırasının tersi (1/rank). Hiç yoksa 0."""
    for i, d in enumerate(ranked, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


# --------------------------- Sıralayıcılar ---------------------------
def tfidf_ranker(descriptions: list[str]):
    """TF-IDF + cosine tabanı (baseline)."""
    vectorizer = TfidfVectorizer()
    doc_matrix = vectorizer.fit_transform(normalize_text(d) for d in descriptions)

    def rank(query: str) -> list[str]:
        q = vectorizer.transform([normalize_text(query)])
        sims = cosine_similarity(q, doc_matrix)[0]
        order = np.argsort(-sims)
        return [descriptions[i] for i in order]

    return rank


def dense_ranker(descriptions: list[str]):
    """Çok dilli embedding + cosine (vektörler birim normlu → iç çarpım = cosine)."""
    doc_vecs = np.array(embed_batch(descriptions))

    def rank(query: str) -> list[str]:
        q = np.array(embed_batch([query])[0])
        sims = doc_vecs @ q
        order = np.argsort(-sims)
        return [descriptions[i] for i in order]

    return rank


def hybrid_ranker(descriptions: list[str], dense_w: float = 0.7, sparse_w: float = 0.3):
    """Dense + BM25 birleşimi (retrieval.hybrid_search'in offline karşılığı)."""
    doc_vecs = np.array(embed_batch(descriptions))
    corpus_tokens = [normalize_text(d).split() for d in descriptions]
    bm25 = BM25Okapi(corpus_tokens)

    def _minmax(arr: np.ndarray) -> np.ndarray:
        lo, hi = float(arr.min()), float(arr.max())
        span = hi - lo
        if span == 0:
            return np.ones_like(arr)
        return (arr - lo) / span

    def rank(query: str) -> list[str]:
        q = np.array(embed_batch([query])[0])
        dense = doc_vecs @ q
        sparse = np.array(bm25.get_scores(normalize_text(query).split()))
        final = dense_w * _minmax(dense) + sparse_w * _minmax(sparse)
        order = np.argsort(-final)
        return [descriptions[i] for i in order]

    return rank


# ------------------------------ Çalıştır ------------------------------
def evaluate(rank_fn, queries: list[dict], k: int) -> dict:
    p, r, rr = [], [], []
    for item in queries:
        ranked = rank_fn(item["query"])
        relevant = set(item["relevant_descriptions"])
        p.append(precision_at_k(ranked, relevant, k))
        r.append(recall_at_k(ranked, relevant, k))
        rr.append(reciprocal_rank(ranked, relevant))
    return {
        f"precision@{k}": float(np.mean(p)),
        f"recall@{k}": float(np.mean(r)),
        "MRR": float(np.mean(rr)),
    }


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    descriptions = df["description"].tolist()
    desc_set = set(descriptions)

    with open(GOLD_PATH, encoding="utf-8") as f:
        gold = json.load(f)
    k = gold.get("k", 3)
    queries = gold["queries"]

    # Tutarlılık kontrolü: her relevant açıklama CSV'de birebir var mı?
    missing = []
    for item in queries:
        for d in item["relevant_descriptions"]:
            if d not in desc_set:
                missing.append((item["query"], d))
    if missing:
        print("UYARI: gold_set'te CSV ile eşleşmeyen açıklamalar var (recall'u düşürür):")
        for q, d in missing:
            print(f"  [{q}] -> {d!r}")
        print()
    else:
        print(f"Tutarlılık OK: {len(queries)} sorgudaki tüm alakalı açıklamalar CSV'de mevcut.\n")

    print(f"Sorgu sayısı: {len(queries)} | Vaka sayısı: {len(descriptions)} | k={k}\n")
    print("Sıralayıcılar hazırlanıyor (embedding üretiliyor)...\n")

    methods = {
        "TF-IDF": tfidf_ranker(descriptions),
        "Dense": dense_ranker(descriptions),
        "Hibrit": hybrid_ranker(descriptions),
    }

    results = {name: evaluate(fn, queries, k) for name, fn in methods.items()}

    # Tablo yazdır.
    metrics = [f"precision@{k}", f"recall@{k}", "MRR"]
    header = f"{'Yöntem':<10}" + "".join(f"{m:>14}" for m in metrics)
    print(header)
    print("-" * len(header))
    for name, scores in results.items():
        row = f"{name:<10}" + "".join(f"{scores[m]:>14.3f}" for m in metrics)
        print(row)
    print()

    _plot(results, metrics)
    print(f"Grafik kaydedildi: {RESULTS_PNG}")

    # Kısa yorum.
    best = max(results, key=lambda n: results[n]["MRR"])
    print(f"\nEn yüksek MRR: {best} ({results[best]['MRR']:.3f})")


def _plot(results: dict, metrics: list[str]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    methods = list(results.keys())
    x = np.arange(len(metrics))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, name in enumerate(methods):
        values = [results[name][m] for m in metrics]
        bars = ax.bar(x + (i - 1) * width, values, width, label=name)
        ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)

    ax.set_ylabel("Skor")
    ax.set_title("AutoDiag — Arama Yöntemleri Karşılaştırması (k=3)")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS_PNG, dpi=120)


if __name__ == "__main__":
    main()
