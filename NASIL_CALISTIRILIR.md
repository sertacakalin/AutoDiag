# AutoDiag — Nasıl Çalıştırılır (Docker)

NLP tabanlı otomotiv arıza teşhis destek sistemi.

## Çalıştır

```bash
cd "/Users/sertacakalin/Desktop/staj proje/autodiag"
docker compose up -d --build
```

İlk açılışta backend, korpusu (971 vaka) DB'ye yükler (~1-2 dk). Sonra:

| Adres | İçerik |
|-------|--------|
| http://localhost:8080 | Arayüz (Vaka Arama + Teşhis Asistanı) |
| http://localhost:8000/docs | API dokümanı |
| http://localhost:8000/health | Durum (mode=db, fault_count) |

## Durdur / Başlat

```bash
docker compose down       # durdur (veri pgdata volume'unda kalır)
docker compose up -d      # tekrar başlat (ingest atlanır, hızlı kalkar)
docker compose logs -f backend   # logları izle
```

## Türkçe-adapte modeli kullan (daha isabetli sonuç)

Varsayılan **base çok dilli model** (384d) çalışır — argo/günlük sorgularda zayıftır.
Eğitilmiş Türkçe modeli (`models/autodiag-embed-tr-hn`) kullanmak için
`docker-compose.yml`'de backend altında şunları aç:

```yaml
    environment:
      EMBED_DIM: "768"
      EMBEDDING_MODEL: "adapted"
    volumes:
      - ./data:/data:ro
      - ./models:/app/models:ro   # ← bu satırı aç
```
Sonra: `docker compose up -d --build backend`

## LLM ile gerçek teşhis önerisi (opsiyonel)

LLM anahtarı yoksa öneri "çıkarımsal" (vakalardan kopya) gelir. Gerçek üretken
öneri için `docker-compose.yml`'de backend environment'a ekle:

```yaml
      LLM_API_KEY: "sk-ant-..."
```

## Notlar

- **Port 5432** makinedeki başka bir Postgres'le çakışırsa db host portu 5433'tedir.
- **Disk:** imajlar ~3 GB yer kaplar; build öncesi yeterli boş alan olduğundan emin ol.
