"""Birim testler: hibrit skorlama, min-max normalize, re-ranking bonusları.

Yalnız-sparse motor (build_dense=False) ile deterministik; embedding gerekmez.
"""

from __future__ import annotations

from app.services.memory_store import FaultRecord, MemoryEngine


def test_minmax_scales_to_unit_range():
    out = MemoryEngine._minmax({"a": 0.0, "b": 5.0, "c": 10.0})
    assert out["a"] == 0.0
    assert out["c"] == 1.0
    assert 0.0 < out["b"] < 1.0


def test_minmax_all_equal_returns_ones():
    out = MemoryEngine._minmax({"a": 3.0, "b": 3.0})
    assert out == {"a": 1.0, "b": 1.0}


def test_minmax_empty_returns_empty():
    assert MemoryEngine._minmax({}) == {}


def test_search_returns_relevant_first(engine):
    hits = engine.search("fren pedalı titriyor", top_k=3)
    assert hits, "sonuç dönmeli"
    assert hits[0].fault.category == "Fren"


def test_search_respects_top_k(engine):
    hits = engine.search("fren titreşim sarsıntı motor", top_k=2)
    assert len(hits) <= 2


def test_search_no_match_returns_empty(engine):
    assert engine.search("xyzzy qwerty zxcvb", top_k=5) == []


def test_dtc_filter_boosts_matching_record(engine):
    q = "fren titreşim ve sarsılıyor"
    base = {h.fault.id: h.similarity for h in engine.search(q, top_k=5)}
    boosted = {h.fault.id: h.similarity for h in engine.search(q, top_k=5, dtc_code="C0040")}
    # r2'nin DTC kodu C0040 → bonus ile skoru artmalı.
    assert boosted["r2"] > base["r2"]


def test_category_filter_boosts_matching_record(engine):
    q = "araç sarsılıyor titreşim"
    base = {h.fault.id: h.similarity for h in engine.search(q, top_k=5)}
    boosted = {h.fault.id: h.similarity for h in engine.search(q, top_k=5, category="Fren")}
    # Fren kategorisindeki kayıtların skoru artmalı.
    assert any(boosted[fid] > base[fid] for fid in base if fid in ("r1", "r2"))


def test_add_grows_corpus_and_is_searchable(engine):
    before = engine.count
    rec = FaultRecord(
        id="new1",
        description="Şanzıman vites geçişinde sertlik ve gecikme",
        category="Şanzıman",
        dtc_code="P0750",
        vehicle_model="Test",
        mileage_km=120_000,
        solution="Solenoid değişti",
    )
    engine.add(rec)
    assert engine.count == before + 1
    hits = engine.search("vites geçişi sertlik gecikme", top_k=3)
    assert any(h.fault.id == "new1" for h in hits)


def test_categories_sorted_unique(engine):
    cats = engine.categories
    assert cats == sorted(set(cats))
    assert "Fren" in cats and "Motor" in cats
