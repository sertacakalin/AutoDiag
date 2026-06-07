"""API bağımlılıkları — motor, geri bildirim deposu ve kimlik doğrulama."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.auth import decode_token
from app.services.memory_store import MemoryEngine

# auto_error=False: header yoksa FastAPI'nin otomatik 401'i yerine kendi 401'imizi
# döndürelim (tutarlı hata biçimi için).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_engine(request: Request) -> MemoryEngine:
    """Uygulama durumundaki arama motorunu döndür."""
    return request.app.state.engine


def get_feedback_store(request: Request) -> list:
    """Bellek-içi geri bildirim listesini döndür (demo amaçlı)."""
    return request.app.state.feedback


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Bearer jetonunu çöz ve ilgili aktif kullanıcıyı DB'den getir.

    Token yok/geçersiz/süresi dolmuş veya kullanıcı bulunamazsa 401 döndürür.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya eksik kimlik bilgisi.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_error

    payload = decode_token(token)
    if not payload:
        raise credentials_error

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    # sub her zaman string; UUID kolonuyla karşılaştırmak için tipini geri çevir.
    try:
        uid: object = UUID(str(user_id))
    except (ValueError, TypeError):
        raise credentials_error

    try:
        user = db.execute(
            select(User).where(User.id == uid)
        ).scalar_one_or_none()
    except Exception:
        # DB hatasında kimliği doğrulanmamış say (detay sızdırma).
        raise credentials_error

    if user is None:
        raise credentials_error

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Yalnız admin rolüne izin ver; aksi halde 403."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli.",
        )
    return user
