"""Faz İ4 — Arıza bilgi grafiğini kur, istatistik yazdır, görselleştir.

Çıktı:
  data/fault_graph.graphml         — graf (yeniden kullanım/inceleme)
  eval/results_graph.png           — bir kategorinin örnek alt-grafiği

Kullanım:  python scripts/build_graph.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.graph import FaultGraph  # noqa: E402

DTC_CSV = ROOT / "data" / "dtc_reference.csv"
GRAPHML = ROOT / "data" / "fault_graph.graphml"
VIZ_PNG = ROOT / "eval" / "results_graph.png"
VIZ_CATEGORY = "Şanzıman"  # görselleştirilecek örnek kategori


def main() -> None:
    fg = FaultGraph.from_dtc_reference(DTC_CSV)
    print("Graf istatistiği:", fg.stats())

    import networkx as nx
    nx.write_graphml(fg.g, GRAPHML)
    print(f"Graf kaydedildi: {GRAPHML}")

    # Örnek teşhis (graf-temelli akıl yürütme).
    print("\nÖrnek graf teşhisi — 'gaza basınca devir yükseliyor ama hızlanmıyor':")
    for d in fg.diagnose("gaza basınca devir yükseliyor ama hızlanmıyor", top_k=3):
        print(f"  {d.dtc_code} ({d.category}, {d.severity}) skor={d.score} | {d.title}")
        print(f"     eşleşen semptom: {', '.join(d.matched_symptoms[:2])}")
        print(f"     olası neden: {', '.join(d.causes[:3])}")

    _viz(fg, VIZ_CATEGORY)
    print(f"\nGörsel: {VIZ_PNG}")


def _viz(fg: FaultGraph, category: str) -> None:
    """Bir kategorinin DTC + semptom + neden alt-grafiğini çiz."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    g = fg.g
    cat_id = f"cat:{category}"
    dtcs = [s for s, _, d in g.in_edges(cat_id, data=True) if d.get("rel") == "IN_CATEGORY"]
    nodes = set(dtcs) | {cat_id}
    for dtc in dtcs:
        for s, _, d in g.in_edges(dtc, data=True):
            if d.get("rel") == "HAS_SYMPTOM":
                nodes.add(s)
        for _, t, d in g.out_edges(dtc, data=True):
            if d.get("rel") == "HAS_CAUSE":
                nodes.add(t)
    sub = g.subgraph(nodes)

    color = {"dtc": "#1f4ed8", "symptom": "#15803d", "cause": "#b45309", "category": "#b42318"}
    size = {"dtc": 600, "symptom": 240, "cause": 240, "category": 800}
    node_colors = [color[sub.nodes[n]["kind"]] for n in sub.nodes]
    node_sizes = [size[sub.nodes[n]["kind"]] for n in sub.nodes]

    def label(n):
        d = sub.nodes[n]
        if d["kind"] == "dtc":
            return d["code"]
        if d["kind"] == "category":
            return d["name"]
        return d["text"][:18]

    pos = nx.spring_layout(sub, k=0.9, seed=42, iterations=80)
    plt.figure(figsize=(13, 9))
    nx.draw_networkx_edges(sub, pos, alpha=0.25, arrows=False)
    nx.draw_networkx_nodes(sub, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_labels(sub, pos, {n: label(n) for n in sub.nodes}, font_size=7)
    plt.title(f"AutoDiag — Arıza Bilgi Grafiği: '{category}' alt-grafiği\n"
              "(mavi=DTC, yeşil=semptom, turuncu=neden, kırmızı=kategori)", fontsize=11)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(VIZ_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
