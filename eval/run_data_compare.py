"""Veri etkisi karşılaştırması (NHTSA gerçek verisi).

Aynı baz model (çok dilli MiniLM) üzerinde TEK değişken VERİ:
  - MiniLM+971(eski):  yalnız Türkçe sentetik korpus (971)
  - MiniLM+4129(yeni): Türkçe + NHTSA gerçek İngilizce şikayetler (4129)

MiniLM-base (eğitimsiz) referans olarak eklenir. Held-out setler (gold_set,
hard_queries) ve metrikler (nDCG@5, MRR) run_model_compare ile aynıdır;
yalnız MODELS ve çıktı grafiği değiştirilir — orijinal İ1 scripti korunur.

Çalıştırma:  cd eval && python run_data_compare.py
"""

import os

import run_model_compare as mc

mc.MODELS = {
    "MiniLM-base": "paraphrase-multilingual-MiniLM-L12-v2",
    "MiniLM+971(eski)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr"),
    "MiniLM+4129(yeni)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr-v2"),
}
mc.OUT_PNG = os.path.join(mc.EVAL_DIR, "results_data_compare.png")

if __name__ == "__main__":
    mc.main()
