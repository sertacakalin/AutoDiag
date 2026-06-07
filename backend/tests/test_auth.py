"""Kimlik doğrulama testleri: kayıt → giriş → /me akışı, koruma ve yetki.

Bu testler bellek-içi SQLite kullanır (conftest db_session/anon_client). Gerçek
Postgres gerektirmez. Şifreler bcrypt ile hash'lenir, jetonlar pyjwt iledir.
"""

from __future__ import annotations


def test_register_login_me_flow(anon_client):
    """İlk kayıt admin olur; giriş yapılır; /me kullanıcıyı döndürür."""
    reg = anon_client.post(
        "/api/auth/register",
        json={"username": "ilk_kullanici", "password": "parola123"},
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    # İlk kullanıcı admin atanmalı.
    assert body["user"]["role"] == "admin"
    assert body["user"]["username"] == "ilk_kullanici"

    # Giriş.
    login = anon_client.post(
        "/api/auth/login",
        json={"username": "ilk_kullanici", "password": "parola123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    # /me — jeton ile.
    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "ilk_kullanici"
    assert me.json()["role"] == "admin"


def test_second_user_is_technician(anon_client):
    """İlk kullanıcıdan sonraki kayıtlar teknisyen olur (admin'e yükseltilemez)."""
    anon_client.post(
        "/api/auth/register",
        json={"username": "admin_user", "password": "parola123"},
    )
    second = anon_client.post(
        "/api/auth/register",
        # Açıkça admin istense bile teknisyen atanmalı (yetki yükseltme önlemi).
        json={"username": "ikinci", "password": "parola123", "role": "admin"},
    )
    assert second.status_code == 201
    assert second.json()["user"]["role"] == "teknisyen"


def test_register_duplicate_username_409(anon_client):
    """Aynı kullanıcı adıyla ikinci kayıt 409 döndürür."""
    anon_client.post(
        "/api/auth/register",
        json={"username": "tekrar", "password": "parola123"},
    )
    dup = anon_client.post(
        "/api/auth/register",
        json={"username": "tekrar", "password": "baska123"},
    )
    assert dup.status_code == 409


def test_login_wrong_password_401(anon_client):
    """Yanlış şifre ile giriş 401 döndürür."""
    anon_client.post(
        "/api/auth/register",
        json={"username": "kullanici", "password": "dogruparola"},
    )
    bad = anon_client.post(
        "/api/auth/login",
        json={"username": "kullanici", "password": "yanlisparola"},
    )
    assert bad.status_code == 401


def test_login_unknown_user_401(anon_client):
    """Var olmayan kullanıcıyla giriş 401 döndürür."""
    r = anon_client.post(
        "/api/auth/login",
        json={"username": "olmayan", "password": "herhangi"},
    )
    assert r.status_code == 401


def test_register_short_password_422(anon_client):
    """6 karakterden kısa şifre validasyondan dönmeli (422)."""
    r = anon_client.post(
        "/api/auth/register",
        json={"username": "kisa", "password": "123"},
    )
    assert r.status_code == 422


def test_protected_endpoint_without_token_401(anon_client):
    """Jetonsuz korunan uca erişim 401 döndürür."""
    r = anon_client.post(
        "/api/search",
        json={"query": "fren titriyor", "rerank": False, "use_rag": False},
    )
    assert r.status_code == 401


def test_me_without_token_401(anon_client):
    """/me jetonsuz 401 döndürür."""
    r = anon_client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_invalid_token_401(anon_client):
    """Geçersiz jeton ile /me 401 döndürür."""
    r = anon_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer gecersiz.jeton.degeri"}
    )
    assert r.status_code == 401


def test_protected_endpoint_with_token_ok(anon_client):
    """Geçerli jeton ile korunan uca erişim başarılı olur."""
    reg = anon_client.post(
        "/api/auth/register",
        json={"username": "yetkili", "password": "parola123"},
    )
    token = reg.json()["access_token"]
    r = anon_client.post(
        "/api/search",
        json={"query": "fren titriyor", "rerank": False, "use_rag": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


def test_admin_only_create_fault_as_admin(anon_client):
    """Admin kullanıcı arıza kaydı oluşturabilir (201)."""
    reg = anon_client.post(
        "/api/auth/register",
        json={"username": "admin_olan", "password": "parola123"},
    )
    assert reg.json()["user"]["role"] == "admin"
    token = reg.json()["access_token"]
    r = anon_client.post(
        "/api/faults",
        json={
            "description": "Egzozdan aşırı duman geliyor",
            "category": "Egzoz",
            "solution": "Katalizör kontrol edildi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201


def test_admin_only_create_fault_as_technician_403(anon_client):
    """Teknisyen kullanıcı arıza kaydı oluşturamaz (403)."""
    # İlk kullanıcı admin, ikinci kullanıcı teknisyen.
    anon_client.post(
        "/api/auth/register",
        json={"username": "ilk_admin", "password": "parola123"},
    )
    tech = anon_client.post(
        "/api/auth/register",
        json={"username": "teknisyen_user", "password": "parola123"},
    )
    assert tech.json()["user"]["role"] == "teknisyen"
    token = tech.json()["access_token"]
    r = anon_client.post(
        "/api/faults",
        json={
            "description": "Egzozdan aşırı duman geliyor",
            "category": "Egzoz",
            "solution": "Katalizör kontrol edildi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_create_fault_without_token_401(anon_client):
    """Jetonsuz arıza oluşturma 401 döndürür."""
    r = anon_client.post(
        "/api/faults",
        json={
            "description": "Egzozdan aşırı duman geliyor",
            "category": "Egzoz",
            "solution": "Katalizör kontrol edildi",
        },
    )
    assert r.status_code == 401


def test_login_rate_limited_after_too_many_attempts(anon_client):
    """Aynı IP'den çok sayıda login denemesi sonunda 429 ile sınırlanır.

    Limiter max_attempts=8/dakika. 8 deneme geçer (401), 9. deneme 429 döner.
    Kovalar autouse fikstürle her test başında temizlendiği için bu izole çalışır.
    """
    statuses = []
    for _ in range(9):
        r = anon_client.post(
            "/api/auth/login",
            json={"username": "olmayan_kullanici", "password": "herhangi"},
        )
        statuses.append(r.status_code)

    # İlk 8 deneme rate-limit'e takılmaz (kullanıcı yok → 401).
    assert statuses[:8] == [401] * 8
    # 9. deneme penceredeki sınırı aşar → 429.
    assert statuses[8] == 429


def test_login_unknown_user_runs_dummy_verify_constant_time(anon_client):
    """Var olmayan kullanıcıda da kukla bcrypt verify çalışır (timing savunması).

    Davranışsal kanıt: var olmayan kullanıcı yine 401 döner ve yanıt, kukla
    hash doğrulaması nedeniyle anlık değil ölçülebilir bir süre alır (bcrypt
    checkpw çağrıldığının dolaylı göstergesi).
    """
    import time

    start = time.perf_counter()
    r = anon_client.post(
        "/api/auth/login",
        json={"username": "kesinlikle_yok", "password": "rastgele_sifre"},
    )
    elapsed = time.perf_counter() - start

    assert r.status_code == 401
    # bcrypt verify (gensalt varsayılan maliyeti) gözlemlenebilir süre alır;
    # eşik düşük tutuldu (CI değişkenliğine dayanıklı) ama anlık-dönüşü dışlar.
    assert elapsed > 0.005
