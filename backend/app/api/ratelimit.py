"""Basit, harici bağımlılıksız, bellek-içi IP başına rate limiter.

Akademik/tek-worker dağıtım için kasıtlı olarak minimal: sliding-window mantığıyla
her IP için son `window` saniyedeki deneme zaman damgalarını bir deque'te tutar.
Çok-worker üretim ortamı için Redis tabanlı bir limiter gerekir; burada amaç
brute-force/enumeration denemelerini tek süreç içinde sınırlamaktır.

Defensive: client bilinmiyorsa "unknown" anahtarı kullanılır; istisna sızdırmaz.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

# IP -> son denemelerin zaman damgaları (saniye). Süreç ömrü boyunca bellekte tutulur.
_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(
    request: Request, *, max_attempts: int = 8, window: int = 60
) -> None:
    """İstemci IP'si için sliding-window rate limit uygula.

    Son `window` saniyede `max_attempts`'tan fazla deneme varsa 429 fırlatır.
    Aksi halde mevcut deneme kaydedilir ve sessizce döner.
    """
    # request.client None olabilir (örn. bazı test/ASGI senaryoları) → savunmacı varsayılan.
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    dq = _BUCKETS[ip]

    # Pencere dışında kalan eski denemeleri at (sliding window).
    while dq and now - dq[0] > window:
        dq.popleft()

    if len(dq) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.",
        )

    dq.append(now)


def reset_buckets() -> None:
    """Tüm rate-limit kovalarını temizle (testler arası izolasyon için)."""
    _BUCKETS.clear()
