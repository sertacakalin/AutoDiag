"""Hedefli veri etkisi: eski adapted model (hn, 971) vs yeni (v3, +hedefli 1155).

Aynı korpus + held-out setlerde (gold_set, hard_queries) hn ve v3'ü karşılaştırır.
trmteb base referans olarak eklenir. run_model_compare makinesini sarmalar.

Çalıştırma: cd eval && python run_targeted_compare.py
"""

import os

import run_model_compare as mc

mc.MODELS = {
    "TR-trmteb-base": "trmteb/turkish-embedding-model",
    "hn (eski·971)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr-hn"),
    "v3 (yeni·1155)": os.path.join(mc.ROOT_DIR, "models", "autodiag-embed-tr-v3"),
}
mc.OUT_PNG = os.path.join(mc.EVAL_DIR, "results_targeted_compare.png")

if __name__ == "__main__":
    mc.main()
