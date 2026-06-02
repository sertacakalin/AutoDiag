"""API bağımlılıkları — paylaşılan motor ve geri bildirim deposuna erişim."""

from __future__ import annotations

from fastapi import Request

from app.services.memory_store import MemoryEngine


def get_engine(request: Request) -> MemoryEngine:
    """Uygulama durumundaki arama motorunu döndür."""
    return request.app.state.engine


def get_feedback_store(request: Request) -> list:
    """Bellek-içi geri bildirim listesini döndür (demo amaçlı)."""
    return request.app.state.feedback
