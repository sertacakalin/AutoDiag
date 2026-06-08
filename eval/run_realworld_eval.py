"""Gerçek dünya (held-out) değerlendirmesi — model argümanlı.

eval/realworld_queries.json içindeki sürücü/usta dili sorgularını
belirtilen model (varsayılan: autodiag-embed-tr-v4) ile HİBRİT +
sorgu genişletme (query_norm) retrieval üzerinden değerlendirir.

Bu set EĞİTİME GİRMEZ; yalnızca ölçüm içindir (sızıntısız, held-out).

Ölçülen metrikler:
  - Kategori top-1 doğruluğu : top-1 sonucun kategorisi == beklenen kategori
  - Kategori top-3 isabeti   : ilk 3 sonuçtan en az biri beklenen kategoride
  - DTC MRR                  : (yalnız dtc_codes verilmiş sorgular için)
                              aynı DTC koduna sahip ilk dokümanın resiprokal sırası

Kategori bazında kırılım yazdırılır; JSON özet eval/realworld_baseline.json'a yazılır.

Çalıştırma:  cd eval && python run_realworld_eval.py [--model autodiag-embed-tr-v4]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

import run_model_compare as mc  # ModelIndex, rank_hybrid_qn, CORPUS_CSV, ROOT_DIR
from app.services.embedding import normalize_text

QUERIES_PATH = os.path.join(mc.EVAL_DIR, "realworld_queries.json")
OUT_JSON = os.path.join(mc.EVAL_DIR, "realworld_baseline.json")
# Varsayılan model v4; --model argümanıyla override edilebilir
_DEFAULT_MODEL = "autodiag-embed-tr-v4"


def reciprocal_rank_codes(ranked: list[int], codes: list[str], target: set[str]) -> float:
    """Aynı DTC koduna sahip ilk dokümanın resiprokal sırası (1/rank)."""
    for i, d in enumerate(ranked, 1):
        if codes[d] in target:
            return 1.0 / i
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerçek dünya held-out değerlendirmesi.")
    parser.add_argument(
        "--model", default=_DEFAULT_MODEL,
        help="Model klasör adı (models/ altında) ya da tam yol. Varsayılan: autodiag-embed-tr-v4"
    )
    args = parser.parse_args()
    model_name = args.model
    # Tam yol verilmemişse models/ altında ara
    if not os.path.isabs(model_name):
        model_path = os.path.join(mc.ROOT_DIR, "models", model_name)
    else:
        model_path = model_name

    # 1) Sorguları yükle
    if not os.path.exists(QUERIES_PATH):
        print(f"HATA: sorgu dosyası yok: {QUERIES_PATH}")
        return 1
    with open(QUERIES_PATH, encoding="utf-8") as f:
        queries = json.load(f)["queries"]
    print(f"Sorgu sayısı: {len(queries)}")

    # 2) Korpusu yükle
    df = pd.read_csv(mc.CORPUS_CSV)
    descs = df["description"].tolist()
    cats = df["category"].tolist()
    codes = df["dtc_code"].fillna("").tolist()
    print(f"Korpus: {len(descs)} vaka")

    # 3) Modeli yükle (dakikalar sürebilir)
    if not os.path.isdir(model_path):
        print(f"HATA: model dizini yok: {model_path}")
        return 1
    try:
        from sentence_transformers import SentenceTransformer

        print(f"Model yükleniyor: {os.path.basename(model_path)} (sabredin)...")
        model = SentenceTransformer(model_path)
    except Exception as exc:  # noqa: BLE001
        print(f"HATA: model yüklenemedi: {exc!r}")
        return 1

    bm25 = BM25Okapi([normalize_text(d).split() for d in descs])
    print("İndeks (embedding) üretiliyor...")
    try:
        idx = mc.ModelIndex(model, descs, bm25)
    except Exception as exc:  # noqa: BLE001
        print(f"HATA: indeks kurulamadı: {exc!r}")
        return 1

    # 4) Değerlendir
    top1_hits = 0
    top3_hits = 0
    dtc_rr: list[float] = []
    per_cat: dict[str, dict] = defaultdict(lambda: {"n": 0, "t1": 0, "t3": 0})
    misses: list[dict] = []

    for q in queries:
        expected = q["category"]
        ranked = mc.rank_hybrid_qn(idx, q["query"])
        top = ranked[:3]
        pred1 = cats[ranked[0]]
        is_t1 = pred1 == expected
        is_t3 = any(cats[d] == expected for d in top)

        top1_hits += int(is_t1)
        top3_hits += int(is_t3)
        per_cat[expected]["n"] += 1
        per_cat[expected]["t1"] += int(is_t1)
        per_cat[expected]["t3"] += int(is_t3)

        rr = None
        if q.get("dtc_codes"):
            rr = reciprocal_rank_codes(ranked, codes, set(q["dtc_codes"]))
            dtc_rr.append(rr)

        if not is_t1:
            misses.append({
                "query": q["query"],
                "expected": expected,
                "got_top1": pred1,
                "top1_desc": descs[ranked[0]][:60],
                "dtc_rr": rr,
            })

    n = len(queries)
    cat_top1 = top1_hits / n
    cat_top3 = top3_hits / n
    dtc_mrr = float(np.mean(dtc_rr)) if dtc_rr else None

    # 5) Yazdır
    print("\n=== GENEL (held-out realworld) ===")
    print(f"Kategori top-1 doğruluğu : {cat_top1*100:5.1f}%  ({top1_hits}/{n})")
    print(f"Kategori top-3 isabeti   : {cat_top3*100:5.1f}%  ({top3_hits}/{n})")
    if dtc_mrr is not None:
        print(f"DTC MRR                  : {dtc_mrr:.3f}  ({len(dtc_rr)} sorgu)")
    else:
        print("DTC MRR                  : yok (dtc_codes'lu sorgu yok)")

    print("\n=== Kategori kırılımı (top-1 | top-3) ===")
    print(f"{'Kategori':<14}{'n':>4}{'top-1':>10}{'top-3':>10}")
    print("-" * 38)
    cat_summary = {}
    for cat in sorted(per_cat):
        c = per_cat[cat]
        t1 = c["t1"] / c["n"]
        t3 = c["t3"] / c["n"]
        cat_summary[cat] = {"n": c["n"], "top1": t1, "top3": t3}
        print(f"{cat:<14}{c['n']:>4}{t1*100:>9.0f}%{t3*100:>9.0f}%")

    if misses:
        print("\n=== top-1 KAÇIRILAN sorgular (sonraki iterasyon hedefi) ===")
        for m in misses:
            print(f"  [{m['expected']:<11}→ {m['got_top1']:<11}] {m['query'][:55]}")
            print(f"      top1: {m['top1_desc']}")

    # 6) JSON özet
    summary = {
        "iteration": 1,
        "model": os.path.basename(model_path),
        "method": "Hibrit+QN (dense 0.7 + bm25 0.3 + query_norm)",
        "n_queries": n,
        "corpus_size": len(descs),
        "category_top1": cat_top1,
        "category_top3": cat_top3,
        "dtc_mrr": dtc_mrr,
        "n_dtc_queries": len(dtc_rr),
        "per_category": cat_summary,
        "misses": misses,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nJSON özet: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
