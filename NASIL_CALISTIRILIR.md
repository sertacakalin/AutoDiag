# AutoDiag — Nasıl Çalıştırılır

Otomotiv arıza teşhis destek sistemi. Hibrit arama (pgvector + BM25) + cross-encoder rerank
+ Türkçe domain-adapte embedding + bilgi grafiği + aktif diyalog teşhis.

> **Ön koşul (doğrulandı):** `backend/.venv` kurulu (fastapi + sentence-transformers hazır),
> `frontend/node_modules` mevcut. Makinede **Docker yok**, o yüzden en pratik yol **Yol 1 (demo)**.

---

## Veri durumu

Yeni dataset indirmeye **gerek yok** — veri hazır ve entegre:

| Dosya | Kayıt | Tür |
|-------|-------|-----|
| `data/faults_dataset.csv` | 971 vaka | Ana korpus (sistemin çalıştığı veri, Türkçe) |
| `data/dtc_reference.csv` | 73 | Gerçek OBD-II DTC kodları (üretimin kaynağı) |
| `data/real/zenodo_faults.csv` | 99 | **Gerçek veri** (Zenodo, CC-BY 4.0, İngilizce) |

Ana korpus, 73 gerçek OBD-II DTC kodundan türetilmiş Türkçe vakalardan oluşur.
Zenodo gerçek verisi çapraz-dilli değerlendirme için kullanılır.

---

## Yol 1 — Demo modu (en kolay, DB gerekmez) ✅ ÖNERİLEN

İki ayrı terminal aç.

### Terminal 1 — Backend (:8000)
```bash
cd "/Users/sertacakalin/Desktop/staj proje/autodiag/backend"
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```
İlk açılışta `data/faults_dataset.csv` (971 vaka) belleğe yüklenir, embedding modeli
cache'ten gelir → bellek-içi hibrit motor (`MemoryEngine`). DB'ye ihtiyaç yoktur.

### Terminal 2 — Frontend (:5173)
```bash
cd "/Users/sertacakalin/Desktop/staj proje/autodiag/frontend"
npm run dev
```

| Adres | İçerik |
|-------|--------|
| http://localhost:5173 | Arayüz (Vaka Arama + Teşhis Asistanı) |
| http://localhost:8000/docs | Swagger API dokümanı |
| http://localhost:8000/health | Sağlık + yetenek durumu |

### Türkçe-adapte embedding (opsiyonel, argo sorgularda daha iyi)
"yatak sesi" gibi günlük-dil sorguların doğru çalışması için domain-adapte modeli kullan:
```bash
# models/autodiag-embed-tr* dizini gerekir (yoksa önce eğit: scripts/finetune_embedding.py)
EMBEDDING_MODEL=adapted EMBED_DIM=768 .venv/bin/python -m uvicorn app.main:app --port 8000
```

---

## Yol 2 — Canlı pgvector (üretim yolu, DB'li)

Docker yok ama makinede `postgresql@17` + pgvector kurulu.

```bash
# 1) pgvector cluster'ını başlat (:5440)
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /tmp/autodiag_pg -o "-p 5440 -k /tmp" start

# 2) Bağlantıyı tanımla
export DATABASE_URL="postgresql+psycopg://autodiag@localhost:5440/autodiag"

# 3) Veriyi DB'ye yükle (971 kayıt embed → DB + HNSW indeksi) — yalnız ilk sefer
cd "/Users/sertacakalin/Desktop/staj proje/autodiag/backend"
.venv/bin/python -m app.services.ingestion

# 4) Backend'i başlat — DB doluysa otomatik DbEngine'e geçer (mode=db)
.venv/bin/python -m uvicorn app.main:app --port 8000
```

---

## Yol 3 — Docker (tek komut)

```bash
docker compose up --build
# Arayüz: http://localhost:8080  ·  API: http://localhost:8000/docs
```
> **Not:** Makinede Docker kurulu değil. Kullanmak için önce Docker Desktop kur.

---

## Test & Kalite

```bash
cd "/Users/sertacakalin/Desktop/staj proje/autodiag/backend"
.venv/bin/python -m pytest          # 30 test
.venv/bin/ruff check .              # lint

cd ../frontend
npm run typecheck                   # TypeScript tip kontrolü
npm run build                       # üretim derlemesi
```

---

## Hızlı duman testi (backend ayaktayken)

```bash
# Sağlık
curl http://localhost:8000/health

# Arama
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"motordan yatak sesi geliyor","top_k":5}'
```

---

## REST uçları

| Metot | Yol | Açıklama |
|-------|-----|----------|
| POST | `/api/search` | Hibrit + rerank + sorgu genişletme araması |
| POST | `/api/faults` | Yeni arıza kaydı ekle |
| POST | `/api/faults/import` | Toplu içe aktar |
| GET | `/api/faults/{id}` | Tek kayıt |
| POST | `/api/feedback` | Sonuç geri bildirimi |
| POST | `/api/diagnose` | GraphRAG yapısal teşhis |
| POST | `/api/diagnose/interactive` | Aktif diyalog teşhis |
| GET | `/health` | Durum + yetenekler |
| GET | `/metrics` | Prometheus metrikleri |
