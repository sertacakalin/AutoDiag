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

    # LLM API anahtarı (Anthropic). Boşsa ve OLLAMA_URL de yoksa RAG katmanı
    # extractive fallback'e düşer.
    LLM_API_KEY: str = ""

    # Ücretsiz YEREL LLM (Ollama). Verilirse Anthropic yerine bu kullanılır;
    # anahtar/internet gerekmez. Örn: http://host.docker.internal:11434
    OLLAMA_URL: str = ""
    OLLAMA_MODEL: str = "aya-expanse:8b"

    # Çok dilli (Türkçe destekli) embedding modeli.
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # JWT kimlik doğrulama ayarları. ÜRETİMDE JWT_SECRET mutlaka ortamdan
    # güçlü bir değerle geçilmelidir; varsayılan yalnız yerel geliştirme içindir.
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ayarları tek sefer yükle ve önbelleğe al.

    Güvenlik fail-safe: JWT_SECRET zayıf/eksikse UYGULAMAYI ÇÖKERTMEZ (testler ve
    yerel çalışma kesintisiz sürsün). Bunun yerine çalışma anında geçici GÜÇLÜ bir
    anahtar üretilir ve uyarı basılır. Aynı cache'li instance hem token üretiminde
    hem de doğrulamada kullanıldığından, üretilen anahtarla imzalanan jetonlar
    süreç boyunca tutarlı kalır. Kalıcı oturumlar için JWT_SECRET ortamdan verilmeli.
    """
    s = Settings()
    # Bilinen zayıf/placeholder değerler veya çok kısa (>=32 zorunlu) anahtarlar.
    _weak = {"", "dev-secret-change-me", "autodiag-local-dev-degistir", "change-me"}
    if s.JWT_SECRET in _weak or len(s.JWT_SECRET) < 32:
        import secrets

        # Pydantic v2 BaseSettings instance'ı mutable; atama güvenle çalışır.
        s.JWT_SECRET = secrets.token_urlsafe(48)
        print(
            "[config] UYARI: zayıf/eksik JWT_SECRET → geçici güçlü anahtar üretildi. "
            "Kalıcı oturumlar için JWT_SECRET ortam değişkenini ayarlayın "
            "(>=32 karakter)."
        )
    return s
