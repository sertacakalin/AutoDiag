"""Entegrasyon testleri: REST uçları (TestClient, DB'siz, model'siz).

Arama isteklerinde rerank=False verilir (cross-encoder yüklenmesin → hızlı).
RAG extractive fallback'tedir (LLM anahtarı yok).
"""

from __future__ import annotations


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["fault_count"] == 5
    assert "Fren" in body["categories"]
    assert body["mode"] in ("sparse", "hybrid")


def test_search_returns_results(client):
    r = client.post("/api/search", json={
        "query": "fren pedalı titriyor", "top_k": 3,
        "rerank": False, "use_rag": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "fren pedalı titriyor"
    assert len(body["results"]) >= 1
    assert body["results"][0]["category"] == "Fren"
    assert body["rag_suggestion"] is not None


def test_search_too_short_query_rejected(client):
    r = client.post("/api/search", json={"query": "ab"})
    assert r.status_code == 422  # min_length=3


def test_search_can_disable_rag(client):
    r = client.post("/api/search", json={
        "query": "klima soğutmuyor", "rerank": False, "use_rag": False,
    })
    assert r.status_code == 200
    assert r.json()["rag_suggestion"] is None


def test_search_query_expansion_reported(client):
    r = client.post("/api/search", json={
        "query": "motor çok kızıyor", "rerank": False,
        "use_rag": False, "expand_query": True,
    })
    assert r.status_code == 200
    expanded = r.json()["expanded_query"]
    assert expanded and "hararet" in expanded.lower()


def test_create_and_get_fault(client):
    create = client.post("/api/faults", json={
        "description": "Egzozdan aşırı duman ve koku geliyor",
        "category": "Egzoz",
        "solution": "Katalizör kontrol edildi",
        "dtc_code": "P0420",
    })
    assert create.status_code == 201
    fid = create.json()["fault_id"]
    assert fid

    got = client.get(f"/api/faults/{fid}")
    assert got.status_code == 200
    assert got.json()["category"] == "Egzoz"


def test_get_unknown_fault_404(client):
    r = client.get("/api/faults/yok-boyle-bir-id")
    assert r.status_code == 404


def test_create_fault_validation_error(client):
    # description çok kısa (<3) → 422
    r = client.post("/api/faults", json={
        "description": "x", "category": "Fren", "solution": "tamam",
    })
    assert r.status_code == 422


def test_feedback_accepted(client):
    # Mevcut bir kaydın id'sini arama ile al.
    search = client.post("/api/search", json={
        "query": "fren titriyor", "rerank": False, "use_rag": False,
    })
    fault_id = search.json()["results"][0]["fault_id"]
    r = client.post("/api/feedback", json={
        "query_text": "fren titriyor",
        "returned_fault_id": fault_id,
        "was_helpful": True,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_feedback_unknown_fault_404(client):
    r = client.post("/api/feedback", json={
        "query_text": "test",
        "returned_fault_id": "olmayan-id",
        "was_helpful": False,
    })
    assert r.status_code == 404
