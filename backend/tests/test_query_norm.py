"""Birim testler: sorgu genişletme (domain gap kapatma)."""

from __future__ import annotations

from app.services.query_norm import expand_query, was_expanded


def test_expand_adds_canonical_terms():
    out = expand_query("motor çok kızıyor")
    # "kızıyor" → kanonik "hararet/aşırı ısınma" eklenir.
    assert "hararet" in out.lower()


def test_expand_preserves_original_query():
    original = "direksiyon taş gibi oldu"
    out = expand_query(original)
    assert out.startswith(original)
    # Kanonik terim eklenmiş olmalı.
    assert len(out) > len(original)
    assert "ağırlaşma" in out.lower() or "sertleşme" in out.lower()


def test_expand_noop_when_no_match():
    q = "qwerty zxcvb"
    assert expand_query(q) == q
    assert was_expanded(q) is False


def test_was_expanded_true_for_slang():
    assert was_expanded("araç stop ediyor") is True


def test_expand_does_not_duplicate_existing_terms():
    # Zaten "hararet" içeren sorguya tekrar eklenmemeli.
    out = expand_query("hararet yapıyor kızıyor")
    assert out.lower().count("hararet") == 1
