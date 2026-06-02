"""Uygulama ayarları — ortam değişkenlerinden okunur (pydantic-settings)."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Embedding vektör boyutu — aktif modelle uyumlu olmalı (DB Vector kolonu için).
# Varsayılan 384 (base MiniLM); Türkçe-adapte model için EMBED_DIM=768 verilir.
EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))


class Settings(BaseSettings):
    """Ortamdan okunan yapılandırma.

    .env dosyası veya ortam değişkenleri ile geçilebilir. Örn:
        DATABASE_URL=postgresql+psycopg://autodiag:autodiag@localhost:5432/autodiag
        LLM_API_KEY=sk-...
        EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Veritabanı bağlantısı (psycopg 3 sürücüsü ile).
    DATABASE_URL: str = (
        "postgresql+psycopg://autodiag:autodiag@localhost:5432/autodiag"
    )

    # LLM API anahtarı. Boşsa RAG katmanı extractive fallback'e düşer.
    LLM_API_KEY: str = ""

    # Çok dilli (Türkçe destekli) embedding modeli.
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ayarları tek sefer yükle ve önbelleğe al."""
    return Settings()
