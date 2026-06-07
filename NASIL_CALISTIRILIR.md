# AutoDiag — Nasıl Çalıştırılır (Docker)

NLP tabanlı otomotiv arıza teşhis destek sistemi. Hibrit arama + Türkçe-adapte
embedding + cross-encoder rerank + bilgi grafiği + diyalog teşhis + yerel LLM (Ollama)
üretken öneri + JWT kimlik doğrulama.

## Ön koşullar

- **Docker Desktop** açık olmalı.
- **Ollama** açık olmalı (AI üretken öneri için). Başlatma: Ollama uygulamasını aç
  veya `ollama serve`. Gerekli model: `aya-expanse:8b` (`ollama pull aya-expanse:8b`).
  > Ollama kapalıysa uygulama yine çalışır; öneri "çıkarımsal" (kopya) moda düşer.

## Çalıştır

```bash
cd "/Users/sertacakalin/Desktop/staj proje/autodiag"
docker compose up -d --build      # ilk kez (build + veri yükleme ~1-2 dk)
```

| Adres | İçerik |
|-------|--------|
| http://localhost:8080 | Arayüz (önce giriş ekranı) |
| http://localhost:8000/docs | API dokümanı |
| http://localhost:8000/health | Durum (mode=db, rag=llm, kayıt sayısı) |

## Giriş / kayıt

İlk açılışta **giriş ekranı** gelir.
1. **Kayıt Ol** → kullanıcı adı + parola (min 6). İLK kayıt olan kullanıcı **admin**,
   sonrakiler **teknisyen** olur. Kayıt sonrası otomatik giriş olmaz; giriş sekmesine
   geçilir.
2. **Giriş Yap** → uygulamaya girilir.

## Kullan

- **Vaka Arama:** arıza belirtisini Türkçe yaz (örn. *"motordan yatak sesi geliyor"*).
  Benzer geçmiş vakalar + **🤖 AI teşhis önerisi** (Ollama) gelir.
- **Teşhis Asistanı:** sistem netleştirici sorular sorup yapısal teşhis verir.
- **Kayıt ekle:** yeni arıza kaydı (yalnız admin).

## Durdur / Başlat / Sıfırla

```bash
docker compose down          # durdur (kullanıcılar + veri pgdata volume'unda kalır)
docker compose up -d         # tekrar başlat (hızlı, ingest atlanır)
docker compose down -v       # SIFIRLA (veri + kullanıcılar silinir; sonraki
                             #          açılışta yeniden ingest + ilk kullanıcı admin)
docker compose logs -f backend   # logları izle
```

## Yapılandırma (docker-compose.yml)

| Değişken | Anlamı |
|----------|--------|
| `EMBED_DIM=768` + `EMBEDDING_MODEL=adapted` | Türkçe-adapte model (autodiag-embed-tr-hn) |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Yerel LLM (host'taki Ollama, aya-expanse) |
| `JWT_SECRET` | JWT imzalama anahtarı. Üretimde: `export JWT_SECRET=<güçlü>` |
| `HF_HOME=/app/.hf` | rerank cross-encoder cache (yazılabilir) |

> **Not:** db host portu 5432 doluysa 5433'tedir. İmajlar ~3 GB yer kaplar.
