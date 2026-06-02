"""Ablation değerlendirmesi: retrieval bileşenlerinin katkısını ölçer.

Karşılaştırılan yöntemler (artımlı):
  1. BM25            — yalnız anahtar kelime (sparse baseline)
  2. Dense           — yalnız çok dilli embedding (semantik)
  3. Hibrit          — dense + BM25 birleşik (mevcut sistem)
  4. Hibrit + Rerank — hibrit aday havuzu + cross-encoder yeniden sıralama

Alaka tanımı (DTC-tabanlı): Bir sonuç, gold sorgunun alakalı vakalarıyla AYNI
DTC koduna sahipse alakalı sayılır. Bu, büyütülmüş korpusta (faults_dataset.csv)
üretilmiş aynı-arıza kayıtlarını da doğru biçimde alakalı kabul eder; birebir
metin eşleşmesine göre çok daha sağlam ve ölçeklenebilir bir ölçüttür.

Metrikler: P@1, P@3, P@5, MRR, nDCG@5. Ayrıca kategori bazında Hibrit→Rerank farkı.
Çıktı: konsol tablosu + eval/results_ablation.png

Çalıştırma:  cd eval && python run_ablation.py
"""

from __future__ import annotations

import math
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from app.services.embedding import embed_batch, normalize_text  # noqa: E402
from app.services.query_norm import expand_query  # noqa: E402
from app.services.rerank import rerank_scores  # noqa: E402

import json  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
SEED_CSV = os.path.join(ROOT_DIR, "data", "faults_seed.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
RESULTS_PNG = os.path.join(EVAL_DIR, "results_ablation.png")
QN_PNG = os.path.join(EVAL_DIR, "results_queryexp.png")

RERANK_POOL = 50  # cross-encoder'a verilecek aday havuzu boyutu
DENSE_W, SPARSE_W = 0.7, 0.3


# ------------------------------- Metrikler -------------------------------
def precision_at_k(ranked: list[int], relevant: set[int], k: int) -> float:
    top = ranked[:k]
    return sum(1 for d in top if d in relevant) / k if top else 0.0


def reciprocal_rank(ranked: list[int], relevant: set[int]) -> float:
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[int], relevant: set[int], k: int) -> float:
    """İkili alaka ile nDCG@k (ranking kalitesi; rerank kazancını iyi yansıtır)."""
    dcg = sum(
        1.0 / math.log2(i + 2) for i, d in enumerate(ranked[:k]) if d in relevant
    )
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal > 0 else 0.0


# ------------------------------ Sıralayıcılar ----------------------------
class Index:
    """Korpus üzerinde paylaşılan dense + sparse indeks (bir kez kurulur)."""

    def __init__(self, descriptions: list[str]):
        self.descriptions = descriptions
        print(f"  embedding üretiliyor ({len(descriptions)} doküman)...")
        self.doc_vecs = np.array(embed_batch(descriptions))
        self.bm25 = BM25Okapi([normalize_text(d).split() for d in descriptions])

    def dense(self, query: str) -> np.ndarray:
        q = np.array(embed_batch([query])[0])
        return self.doc_vecs @ q

    def sparse(self, query: str) -> np.ndarray:
        return np.array(self.bm25.get_scores(normalize_text(query).split()))


def _minmax(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    span = hi - lo
    return np.ones_like(arr) if span == 0 else (arr - lo) / span


def rank_bm25(idx: Index, query: str) -> list[int]:
    return list(np.argsort(-idx.sparse(query)))


def rank_dense(idx: Index, query: str) -> list[int]:
    return list(np.argsort(-idx.dense(query)))


def rank_hybrid(idx: Index, query: str) -> list[int]:
    final = DENSE_W * _minmax(idx.dense(query)) + SPARSE_W * _minmax(idx.sparse(query))
    return list(np.argsort(-final))


def rank_hybrid_rerank(idx: Index, query: str) -> list[int]:
    """Hibrit ile top-N aday → cross-encoder ile yeniden sırala."""
    base = rank_hybrid(idx, query)
    pool = base[:RERANK_POOL]
    scores = rerank_scores(query, [idx.descriptions[i] for i in pool])
    if scores is None:  # reranker yok → hibrit sırası
        return base
    order = np.argsort(-np.array(scores))
    reranked = [pool[i] for i in order]
    return reranked + base[RERANK_POOL:]


def rank_hybrid_qn(idx: Index, query: str) -> list[int]:
    """Sorgu genişletme + hibrit (1. aşama)."""
    return rank_hybrid(idx, expand_query(query))


def rank_hybrid_rerank_qn(idx: Index, query: str) -> list[int]:
    """Genişletilmiş sorgu ile 1. aşama; rerank DOĞAL (orijinal) sorgu ile."""
    base = rank_hybrid(idx, expand_query(query))
    pool = base[:RERANK_POOL]
    scores = rerank_scores(query, [idx.descriptions[i] for i in pool])
    if scores is None:
        return base
    order = np.argsort(-np.array(scores))
    return [pool[i] for i in order] + base[RERANK_POOL:]


METHODS = {
    "BM25": rank_bm25,
    "Dense": rank_dense,
    "Hibrit": rank_hybrid,
    "Hibrit+Rerank": rank_hybrid_rerank,
}

# Sorgu genişletme (QN) etkisini izole etmek için karşılaştırma çiftleri.
QN_METHODS = {
    "Hibrit": rank_hybrid,
    "Hibrit+QN": rank_hybrid_qn,
    "Hibrit+Rerank": rank_hybrid_rerank,
    "Hibrit+Rerank+QN": rank_hybrid_rerank_qn,
}


# ----------------------------- Alaka kümeleri ----------------------------
def build_relevance(df: pd.DataFrame, queries: list[dict]) -> list[dict]:
    """Her sorgu için DTC-tabanlı alakalı doküman indekslerini hesapla."""
    desc_to_idx: dict[str, int] = {}
    for i, d in enumerate(df["description"].tolist()):
        desc_to_idx.setdefault(d, i)
    codes = df["dtc_code"].fillna("").tolist()
    cats = df["category"].tolist()

    enriched = []
    for item in queries:
        # İki gold formatı: 'relevant_descriptions' (metin) veya 'dtc_codes' (kod).
        if "dtc_codes" in item:
            rel_codes = {c for c in item["dtc_codes"] if c}
            relevant = {i for i, c in enumerate(codes) if c in rel_codes}
        else:
            exact = item.get("relevant_descriptions", [])
            exact_idx = {desc_to_idx[d] for d in exact if d in desc_to_idx}
            rel_codes = {codes[i] for i in exact_idx if codes[i]}
            relevant = set(exact_idx)
            if rel_codes:
                relevant |= {i for i, c in enumerate(codes) if c in rel_codes}
        # Sorguya bir kategori ata (alakalı vakaların çoğunluğu).
        cat = Counter(cats[i] for i in relevant).most_common(1)[0][0] if relevant else "?"
        enriched.append({"query": item["query"], "relevant": relevant, "category": cat})
    return enriched


# -------------------------------- Çalıştır -------------------------------
def evaluate(rank_fn, idx: Index, queries: list[dict]) -> dict:
    p1, p3, p5, mrr, ndcg = [], [], [], [], []
    for item in queries:
        ranked = rank_fn(idx, item["query"])
        rel = item["relevant"]
        p1.append(precision_at_k(ranked, rel, 1))
        p3.append(precision_at_k(ranked, rel, 3))
        p5.append(precision_at_k(ranked, rel, 5))
        mrr.append(reciprocal_rank(ranked, rel))
        ndcg.append(ndcg_at_k(ranked, rel, 5))
    return {
        "P@1": float(np.mean(p1)),
        "P@3": float(np.mean(p3)),
        "P@5": float(np.mean(p5)),
        "MRR": float(np.mean(mrr)),
        "nDCG@5": float(np.mean(ndcg)),
    }


def per_category(idx: Index, queries: list[dict]) -> dict:
    """Hibrit vs Hibrit+Rerank: kategori bazında nDCG@5."""
    cats = sorted({q["category"] for q in queries})
    out = {}
    for cat in cats:
        subset = [q for q in queries if q["category"] == cat]
        h = evaluate(rank_hybrid, idx, subset)["nDCG@5"]
        r = evaluate(rank_hybrid_rerank, idx, subset)["nDCG@5"]
        out[cat] = (len(subset), h, r)
    return out


METRICS = ["P@1", "P@3", "P@5", "MRR", "nDCG@5"]


def _table(results: dict, width: int = 18) -> None:
    header = f"{'Yöntem':<{width}}" + "".join(f"{m:>9}" for m in METRICS)
    print(header)
    print("-" * len(header))
    for name, sc in results.items():
        print(f"{name:<{width}}" + "".join(f"{sc[m]:>9.3f}" for m in METRICS))


def run_suite(idx: Index, queries: list[dict], title: str) -> dict:
    """Bir sorgu seti üzerinde 4 çekirdek yöntemi değerlendir ve tabloyu yazdır."""
    print(f"\n=== {title} ===")
    avg_rel = np.mean([len(q["relevant"]) for q in queries])
    print(f"Sorgu: {len(queries)} | ort. alakalı vaka/sorgu: {avg_rel:.1f}\n")
    results = {name: evaluate(fn, idx, queries) for name, fn in METHODS.items()}
    _table(results)
    return results


def run_qn(idx: Index, queries: list[dict], title: str) -> dict:
    """Sorgu genişletme (QN) etkisini izole eden karşılaştırma tablosu."""
    print(f"\n--- Sorgu genişletme etkisi: {title} ---")
    res = {name: evaluate(fn, idx, queries) for name, fn in QN_METHODS.items()}
    _table(res)
    d = res["Hibrit+QN"]["nDCG@5"] - res["Hibrit"]["nDCG@5"]
    dm = res["Hibrit+QN"]["MRR"] - res["Hibrit"]["MRR"]
    print(f"QN kazancı (Hibrit → +QN): nDCG@5 {'+' if d>=0 else ''}{d:.3f} | "
          f"MRR {'+' if dm>=0 else ''}{dm:.3f}")
    return res


def main() -> None:
    df = pd.read_csv(CORPUS_CSV)
    descriptions = df["description"].tolist()
    print(f"Korpus: {len(descriptions)} vaka ({os.path.basename(CORPUS_CSV)})")
    print("Alaka ölçütü: aynı DTC kodu (+ birebir gold metni)")

    with open(GOLD_PATH, encoding="utf-8") as f:
        std_q = build_relevance(df, json.load(f)["queries"])

    idx = Index(descriptions)

    # 1) Standart gold seti.
    results = run_suite(idx, std_q, "Standart sorgular (gold_set)")

    base, rr = results["Hibrit"], results["Hibrit+Rerank"]
    print("\nRerank kazancı (Hibrit → +Rerank):")
    for m in METRICS:
        d = rr[m] - base[m]
        print(f"  {m:<8} {base[m]:.3f} → {rr[m]:.3f}  ({'+' if d >= 0 else ''}{d:.3f})")

    run_qn(idx, std_q, "Standart sorgular")

    # 2) Zorlu (paraphrase/argo) seti — lexical vs semantik dayanıklılık.
    if os.path.exists(HARD_PATH):
        with open(HARD_PATH, encoding="utf-8") as f:
            hard_q = build_relevance(df, json.load(f)["queries"])
        hard_results = run_suite(idx, hard_q, "Zorlu sorgular (argo/paraphrase)")
        b, r = hard_results["BM25"]["nDCG@5"], hard_results["Hibrit+Rerank"]["nDCG@5"]
        print(f"\nDayanıklılık (nDCG@5): BM25 {b:.3f} → Hibrit+Rerank {r:.3f} "
              f"({'+' if r - b >= 0 else ''}{r - b:.3f})")
        hard_qn = run_qn(idx, hard_q, "Zorlu sorgular")
        _plot_single(
            hard_qn, METRICS,
            "Sorgu genişletme etkisi — zorlu (argo) sorgular",
            QN_PNG,
        )
        print(f"QN grafiği: {QN_PNG}")

    print("\nKategori bazında nDCG@5 (standart set, Hibrit → +Rerank):")
    for cat, (n, h, r) in per_category(idx, std_q).items():
        print(f"  {cat:<14} (n={n})  {h:.3f} → {r:.3f}")

    hard = hard_results if os.path.exists(HARD_PATH) else None
    _plot(results, hard, METRICS)
    print(f"\nGrafik: {RESULTS_PNG}")


def _panel(ax, results: dict, metrics: list[str], title: str) -> None:
    methods = list(results.keys())
    x = np.arange(len(metrics))
    width = 0.2
    for i, name in enumerate(methods):
        vals = [results[name][m] for m in metrics]
        bars = ax.bar(x + (i - 1.5) * width, vals, width, label=name)
        ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=6)
    ax.set_title(title, fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", alpha=0.3)


def _plot_single(results: dict, metrics: list[str], title: str, path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    _panel(ax, results, metrics, title)
    ax.set_ylabel("Skor")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.07), fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")


def _plot(std: dict, hard: dict | None, metrics: list[str]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = 2 if hard else 1
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 5.0), squeeze=False)
    _panel(axes[0][0], std, metrics, "Standart sorgular (temiz)")
    axes[0][0].set_ylabel("Skor")
    if hard:
        _panel(axes[0][1], hard, metrics, "Zorlu sorgular (argo/paraphrase)")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.suptitle("AutoDiag — Retrieval Ablation (DTC-tabanlı alaka)", y=1.0, fontsize=12)
    fig.legend(handles, labels, ncol=4, loc="lower center", fontsize=9,
               bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    fig.savefig(RESULTS_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
