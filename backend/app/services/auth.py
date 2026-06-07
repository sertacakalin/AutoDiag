"""Kimlik doğrulama yardımcıları: şifre hash'leme ve JWT üretimi/çözümü.

Defensive kod: her fonksiyon try/except ile sarılıdır. passlib KULLANILMAZ —
bcrypt doğrudan kullanılır (sürüm çakışması yaşanmasın diye).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(pw: str) -> str:
    """Düz metin şifreyi bcrypt ile hash'le ve string olarak döndür."""
    if not isinstance(pw, str) or pw == "":
        raise ValueError("Şifre boş olamaz.")
    # bcrypt 72 bayttan uzun girdileri sessizce keser; yine de bytes'a çeviriyoruz.
    pw_bytes = pw.encode("utf-8")
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    """Düz şifrenin verilen hash ile eşleşip eşleşmediğini güvenli kontrol et."""
    try:
        if not pw or not hashed:
            return False
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Bozuk/biçimsiz hash → eşleşme yok (asla istisna sızdırma).
        return False


def create_access_token(sub: str, role: str) -> str:
    """Verilen kullanıcı (sub) ve rol için imzalı bir JWT erişim jetonu üret."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(sub),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """JWT'yi çöz ve payload'ı döndür; geçersiz/süresi dolmuş ise None."""
    if not token:
        return None
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        # Süresi dolmuş, imza hatalı, biçimsiz vb. → sessizce None.
        return None
    except Exception:
        # Beklenmeyen her durumda da güvenli tarafta kal.
        return None
