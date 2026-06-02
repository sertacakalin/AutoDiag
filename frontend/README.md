# AutoDiag — Frontend (Faz 9)

Otomotiv arıza teşhis destek sisteminin web arayüzü. React + Vite + TypeScript,
harici UI kütüphanesi yok; tasarım belirteçleri (CSS değişkenleri) + CSS Modules.

## Mimari

```
src/
  api/
    types.ts      Backend şemalarıyla eşleşen tipler
    client.ts     fetch sarmalayıcı, hata çevirimi, ApiError
  components/
    SearchPanel       Arıza tanımı + kategori/DTC/sonuç filtreleri (⌘↵)
    ResultList        Sonuç kartları: benzerlik göstergesi, çözüm, geri bildirim
    SuggestionCard    RAG teşhis önerisi (olası neden, adımlar, güven)
    AddFaultDrawer    Yeni kayıt ekleme (slide-over form)
    EmptyState        Örnek sorgular
    Toast             Bildirim
    ui/Primitives     DtcCode, CategoryTag, ConfidenceBadge, SimilarityMeter
  styles/tokens.css   Tasarım sistemi (renk, tipografi, gölge, yarıçap)
  App.tsx             Orkestrasyon: arama, durum, düzen
```

## Çalıştırma

Önce backend ayakta olmalı:

```bash
# 1) Backend (autodiag/backend)
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 2) Frontend (autodiag/frontend)
npm install
npm run dev          # http://localhost:5173
```

API adresi varsayılan `http://localhost:8000`. Değiştirmek için `.env`:

```
VITE_API_URL=http://localhost:8000
```

## Komutlar

| Komut | Açıklama |
|-------|----------|
| `npm run dev` | Geliştirme sunucusu (HMR) |
| `npm run build` | Tip kontrolü + üretim derlemesi (`dist/`) |
| `npm run preview` | Üretim derlemesini önizle |
| `npm run typecheck` | Yalnız TypeScript tip kontrolü |

## Notlar

- Arayüz, backend `/health` ucundan kategori listesini ve aktif arama modunu
  (hibrit/sparse) canlı okur — hiçbir liste arayüzde sabit kodlanmamıştır.
- Mobil uyumlu; klavye erişilebilirliği (odak halkaları, ⌘↵, Esc) gözetildi.
- `prefers-reduced-motion` tercihine saygı duyulur.
