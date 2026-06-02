"""Faz İ4 — Arıza Bilgi Grafiği (Knowledge Graph).

Gerçek OBD-II DTC referansından yapısal bir graf kurar:

    (Symptom) --HAS_SYMPTOM-- (DTC) --HAS_CAUSE-- (Cause)
                                |
                           IN_CATEGORY
                                |
                           (Category)

Bu graf, saf metin retrieval'ından farklı olarak **yapısal akıl yürütme** sağlar:
serbest bir semptom metni → eşleşen semptom düğümleri → bağlı DTC'ler → olası
nedenler. Sonuçlar neden-sonuç yollarına dayandığından (GraphRAG, Faz İ5)
halüsinasyon riski düşer.

Semptom eşleştirme embedding benzeliğiyle yapılır (model lazy yüklenir).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx


def _split(field_val: str) -> list[str]:
    return [p.strip() for p in (field_val or "").split(";") if p.strip()]


@dataclass
class Diagnosis:
    """Graf-temelli bir teşhis adayı."""

    dtc_code: str
    title: str
    category: str
    severity: str
    score: float
    causes: list[str] = field(default_factory=list)
    matched_symptoms: list[str] = field(default_factory=list)


class FaultGraph:
    """DTC referansından kurulan arıza bilgi grafiği."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.g = graph
        self._symptom_nodes: list[str] = [
            n for n, d in graph.nodes(data=True) if d.get("kind") == "symptom"
        ]
        self._symptom_vecs = None  # lazy

    # ---------------------------------------------------------------- kurulum
    @classmethod
    def from_dtc_reference(cls, csv_path: str | Path) -> "FaultGraph":
        g = nx.MultiDiGraph()
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                code = (row.get("dtc_code") or "").strip()
                if not code:
                    continue
                dtc_id = f"dtc:{code}"
                # Aynı kod birden çok satırda olabilir (farklı kategori/bağlam).
                g.add_node(
                    dtc_id, kind="dtc", code=code,
                    title=(row.get("title_tr") or "").strip(),
                    severity=(row.get("severity") or "").strip(),
                )
                cat = (row.get("category") or "").strip()
                if cat:
                    cat_id = f"cat:{cat}"
                    g.add_node(cat_id, kind="category", name=cat)
                    g.add_edge(dtc_id, cat_id, rel="IN_CATEGORY")
                for s in _split(row.get("symptoms_tr", "")):
                    sid = f"sym:{s.lower()}"
                    g.add_node(sid, kind="symptom", text=s)
                    g.add_edge(sid, dtc_id, rel="HAS_SYMPTOM")
                for c in _split(row.get("causes_tr", "")):
                    cid = f"cause:{c.lower()}"
                    g.add_node(cid, kind="cause", text=c)
                    g.add_edge(dtc_id, cid, rel="HAS_CAUSE")
        return cls(g)

    # --------------------------------------------------------------- istatistik
    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        for _, d in self.g.nodes(data=True):
            kinds[d.get("kind", "?")] = kinds.get(d.get("kind", "?"), 0) + 1
        return {"nodes": self.g.number_of_nodes(), "edges": self.g.number_of_edges(), **kinds}

    # ----------------------------------------------------------------- eşleşme
    def _ensure_symptom_vecs(self):
        if self._symptom_vecs is None:
            from app.services.embedding import embed_batch

            texts = [self.g.nodes[n]["text"] for n in self._symptom_nodes]
            self._symptom_vecs = embed_batch(texts) if texts else []

    def diagnose(self, query: str, top_k: int = 5, sym_top: int = 6) -> list[Diagnosis]:
        """Serbest semptom metninden graf üzerinden olası DTC/neden çıkar.

        1. Sorguyu semptom düğümleriyle embedding benzerliğiyle eşle (top-N).
        2. Eşleşen semptomlardan HAS_SYMPTOM kenarlarıyla DTC'lere geç; DTC skoru
           = bağlı semptom benzerliklerinin toplamı.
        3. Her DTC için HAS_CAUSE ile nedenleri topla; skora göre sırala.
        """
        import numpy as np

        from app.services.embedding import embed

        self._ensure_symptom_vecs()
        if not self._symptom_nodes:
            return []

        qv = np.array(embed(query))
        sims = np.array(self._symptom_vecs) @ qv
        top_idx = np.argsort(-sims)[:sym_top]

        dtc_score: dict[str, float] = {}
        dtc_syms: dict[str, list[str]] = {}
        for i in top_idx:
            sim = float(sims[i])
            if sim <= 0:
                continue
            snode = self._symptom_nodes[i]
            stext = self.g.nodes[snode]["text"]
            for _, dtc_id, d in self.g.out_edges(snode, data=True):
                if d.get("rel") != "HAS_SYMPTOM":
                    continue
                dtc_score[dtc_id] = dtc_score.get(dtc_id, 0.0) + sim
                dtc_syms.setdefault(dtc_id, []).append(stext)

        ranked = sorted(dtc_score.items(), key=lambda x: x[1], reverse=True)[:top_k]
        out: list[Diagnosis] = []
        for dtc_id, score in ranked:
            node = self.g.nodes[dtc_id]
            causes = [
                self.g.nodes[c]["text"]
                for _, c, d in self.g.out_edges(dtc_id, data=True)
                if d.get("rel") == "HAS_CAUSE"
            ]
            cat = next(
                (self.g.nodes[c]["name"] for _, c, d in self.g.out_edges(dtc_id, data=True)
                 if d.get("rel") == "IN_CATEGORY"),
                "",
            )
            out.append(Diagnosis(
                dtc_code=node["code"], title=node.get("title", ""),
                category=cat, severity=node.get("severity", ""),
                score=round(score, 4), causes=causes,
                matched_symptoms=dtc_syms.get(dtc_id, []),
            ))
        return out

    def dtc_detail(self, code: str) -> dict:
        """Bir DTC'nin tam yapısal detayı (başlık, kategori, önem, nedenler)."""
        dtc_id = f"dtc:{code}"
        if dtc_id not in self.g:
            return {}
        node = self.g.nodes[dtc_id]
        sub = self.subgraph_for_dtc(code)
        return {
            "dtc_code": code,
            "title": node.get("title", ""),
            "severity": node.get("severity", ""),
            "category": sub.get("category", ""),
            "causes": sub.get("causes", []),
            "symptoms": sub.get("symptoms", []),
        }

    def subgraph_for_dtc(self, code: str) -> dict:
        """Bir DTC'nin komşuluğu (semptomlar, nedenler, kategori)."""
        dtc_id = f"dtc:{code}"
        if dtc_id not in self.g:
            return {}
        symptoms = [self.g.nodes[s]["text"] for s, _, d in self.g.in_edges(dtc_id, data=True)
                    if d.get("rel") == "HAS_SYMPTOM"]
        causes, category = [], ""
        for _, t, d in self.g.out_edges(dtc_id, data=True):
            if d.get("rel") == "HAS_CAUSE":
                causes.append(self.g.nodes[t]["text"])
            elif d.get("rel") == "IN_CATEGORY":
                category = self.g.nodes[t]["name"]
        return {"dtc": code, "category": category, "symptoms": symptoms, "causes": causes}
