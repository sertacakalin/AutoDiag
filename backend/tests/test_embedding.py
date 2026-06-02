"""Birim testler: metin normalizasyonu ve embedding boyutu."""

from __future__ import annotations

import pytest

from app.config import EMBED_DIM
from app.services.embedding import normalize_text


def test_normalize_lowercases_and_trims():
    assert normalize_text("  Motor   Titriyor  ") == "motor titriyor"


def test_normalize_collapses_inner_whitespace():
    assert normalize_text("fren\t\n  pedalı") == "fren pedalı"


def test_normalize_preserves_turkish_chars():
    out = normalize_text("ÇĞİÖŞÜ çğıöşü")
    # Türkçe karakterler korunur (yalnız küçük harfe çevrilir).
    assert "ç" in out and "ğ" in out and "ö" in out and "ş" in out and "ü" in out


def test_normalize_empty_returns_empty():
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_embed_dimension_is_384():
    """embed() 384 boyutlu vektör döndürür (model cache'liyse)."""
    try:
        from app.services.embedding import embed

        vec = embed("motor titriyor")
    except Exception as exc:  # model indirilemiyor (çevrimdışı) → atla
        pytest.skip(f"embedding modeli yüklenemedi: {exc}")
    assert isinstance(vec, list)
    assert len(vec) == EMBED_DIM == 384
    assert all(isinstance(x, float) for x in vec[:5])
