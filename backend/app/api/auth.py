"""Kimlik doğrulama uçları: kayıt, giriş ve aktif kullanıcı bilgisi.

İlk kaydolan kullanıcı otomatik olarak "admin" rolünü alır; sonrakiler
"teknisyen" olur. Şifreler bcrypt ile hash'lenir, asla düz saklanmaz.
"""

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.ratelimit import rate_limit
from app.db import get_db
from app.models import User
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Kabul edilen roller (istenirse açıkça verilebilir; ilk kullanıcı yine admin olur).
_VALID_ROLES = {"teknisyen", "admin"}

# Timing-enumeration savunması için önceden hesaplanmış kukla bcrypt hash'i.
# Kullanıcı yoksa da bu hash'e karşı verify çalıştırarak yanıt süresini sabitleriz;
# böylece saldırgan "kullanıcı var mı yok mu" bilgisini zamanlama farkından çıkaramaz.
_DUMMY_HASH = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode("utf-8")


def _to_user_response(user: User) -> UserResponse:
    """User modelini dışa açık şemaya çevir (hash sızdırmaz)."""
    return UserResponse(id=str(user.id), username=user.username, role=user.role)


def _token_for(user: User) -> TokenResponse:
    """Bir kullanıcı için TokenResponse üret."""
    token = create_access_token(sub=str(user.id), role=user.role)
    return TokenResponse(access_token=token, user=_to_user_response(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Yeni kullanıcı oluştur. Kullanıcı adı benzersiz olmalı (çakışırsa 409)."""
    # Kötüye kullanım/spam kayıt denemelerini IP başına sınırla.
    rate_limit(request)
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="Kullanıcı adı boş olamaz.")

    # Benzersizlik kontrolü.
    existing = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kullanıcı adı zaten kullanımda.",
        )

    # İlk kullanıcı admin; sonrakiler teknisyen (açık rol verilse de güvenlik gereği
    # ilk kayıt admin olur, ek admin'i ancak mevcut bir admin oluşturmalıdır).
    user_count = db.execute(select(func.count()).select_from(User)).scalar_one()
    if user_count == 0:
        role = "admin"
    else:
        role = payload.role if payload.role in _VALID_ROLES else "teknisyen"
        # Açık uçtan admin atamasına izin verme (yetki yükseltmesini önle).
        if role == "admin":
            role = "teknisyen"

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        # Yarış durumunda benzersizlik ihlali olabilir → 409.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıt oluşturulamadı (kullanıcı adı çakışması).",
        ) from exc
    db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Kullanıcı adı/şifre ile giriş yap; başarısızsa 401."""
    # Brute-force denemelerini IP başına sınırla.
    rate_limit(request)

    user = db.execute(
        select(User).where(User.username == payload.username.strip())
    ).scalar_one_or_none()

    # Timing-enumeration savunması: kullanıcı yoksa bile sabit-zaman için kukla
    # hash'e karşı verify çalıştır; böylece "kullanıcı var mı" zamanlamadan sızmaz.
    pw_ok = verify_password(
        payload.password, user.password_hash if user else _DUMMY_HASH
    )
    if user is None or not pw_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı.",
        )
    return _token_for(user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    """Geçerli jetona ait aktif kullanıcının bilgisini döndür."""
    return _to_user_response(user)
