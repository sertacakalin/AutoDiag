"""S5 — Deney sonuçlarını MLflow'a kaydeder (deney kayıt defteri).

Model karşılaştırması ve ablation sonuçlarını MLflow'a (sqlite backend) yazar;
`mlflow ui` ile pano olarak görüntülenir. finetune_embedding.py her eğitimi
ayrıca otomatik loglar.

Çalıştırma:  python scripts/log_experiments.py    (sonra: mlflow ui --backend-store-uri sqlite:///mlflow.db)
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (model, hard_negative?, standart_dense_nDCG, zorlu_hibritQN_nDCG, ses_ayrım_acc)
MODEL_RESULTS = [
    ("MiniLM-base", False, 0.651, 0.225, 0.60),
    ("TR-trmteb", False, 0.769, 0.275, 0.70),
    ("TR-trmteb-adapte", False, 0.810, 0.526, 0.70),
    ("TR-adapte-HN", True, 0.824, 0.366, 0.90),
]


def main() -> None:
    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{ROOT / 'mlflow.db'}")
    mlflow.set_experiment("autodiag-embedding-comparison")

    for name, hn, std, hard, noise in MODEL_RESULTS:
        with mlflow.start_run(run_name=name):
            mlflow.log_params({"model": name, "hard_negative": hn})
            mlflow.log_metrics({
                "standart_dense_ndcg": std,
                "zorlu_hibritqn_ndcg": hard,
                "ses_ayrim_acc": noise,
            })
    print(f"{len(MODEL_RESULTS)} model çalıştırması MLflow'a kaydedildi "
          f"({ROOT / 'mlflow.db'}).")
    print("Görüntüle:  mlflow ui --backend-store-uri sqlite:///mlflow.db")


if __name__ == "__main__":
    main()
