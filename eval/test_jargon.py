"""Doğrudan jargon testi: 'ön takım' vb. argo sorgular hn vs v3 ile.

Hibrit + sorgu genişletme (query_norm) aktif. Top-1 sonucun kategorisini gösterir
— hedefli veri + jargon sözlüğünün argo sorguları doğru sisteme götürüp götürmediği.

Çalıştırma: cd eval && python test_jargon.py
"""

import os

import pandas as pd
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

import run_model_compare as mc
from app.services.embedding import normalize_text

# (sorgu, beklenen kategori) — argo/günlük dil
QUERIES = [
    ("golf 7.5 aracımda ön takımdan ses geliyor", "Süspansiyon/Direksiyon"),
    ("rotbaşından tıkırtı geliyor virajda", "Direksiyon"),
    ("kasis geçerken z rottan zınk sesi", "Süspansiyon"),
    ("tekerlekten uğultu hızlandıkça artıyor", "Süspansiyon"),
    ("direksiyon kırınca ön taraftan tak tak ses", "Direksiyon"),
    ("amortisör bitti araç zıp zıp yapıyor", "Süspansiyon"),
]

MODELS = {
    "hn (eski·971)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr-hn"),
    "v3 (iter0·1155)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr-v3"),
    "v4 (iter1)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr-v4"),
}


def main() -> None:
    df = pd.read_csv(mc.CORPUS_CSV)
    descs = df["description"].tolist()
    cats = df["category"].tolist()
    bm25 = BM25Okapi([normalize_text(d).split() for d in descs])

    for name, ref in MODELS.items():
        if not os.path.isdir(ref):
            print(f"\n=== {name} — ATLA (model yok: {ref}) ===")
            continue
        idx = mc.ModelIndex(SentenceTransformer(ref), descs, bm25)
        print(f"\n=== {name} ===")
        for q, expected in QUERIES:
            ranked = mc.rank_hybrid_qn(idx, q)  # hibrit + sorgu genişletme
            top = ranked[0]
            print(f"  beklenen [{expected}] → [{cats[top]}]  {descs[top][:48]}")


if __name__ == "__main__":
    main()
