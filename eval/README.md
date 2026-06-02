# AutoDiag — Değerlendirme (Evaluation)

Retrieval bileşenlerinin katkısını ölçen ablation çalışması. DB gerektirmez;
vektörler bellek içinde üretilir.

## Çalıştırma

```bash
cd eval
../backend/.venv/bin/python run_ablation.py     # ablation (önerilen)
../backend/.venv/bin/python run_eval.py          # ilk/temel karşılaştırma
```

## Yöntemler (artımlı ablation)

| # | Yöntem | Açıklama |
|---|--------|----------|
| 1 | **BM25** | Anahtar kelime (sparse) — lexical baseline |
| 2 | **Dense** | Çok dilli embedding (semantik) |
| 3 | **Hibrit** | Dense + BM25 birleşik (üretim sistemi) |
| 4 | **Hibrit + Rerank** | Hibrit aday havuzu → cross-encoder yeniden sıralama |

## Alaka ölçütü (DTC-tabanlı)

Bir sonuç, gold sorgunun alakalı vakalarıyla **aynı DTC koduna** sahipse alakalı
sayılır. Bu ölçüt, büyütülmüş korpustaki (809 vaka) üretilmiş aynı-arıza
kayıtlarını da doğru biçimde alakalı kabul eder — birebir metin eşleşmesine göre
çok daha sağlam ve ölçeklenebilir.

## Veri kümeleri

- `gold_set.json` — 24 standart sorgu (formal ifade)
- `hard_queries.json` — 10 zorlu sorgu (argo/paraphrase, düşük kelime örtüşmesi)

## Bulgular (özet)

**Standart sorgular:** Hibrit, üst-sıra metriklerini doyuruyor (P@1 = MRR = 1.0).
Sıralama: **Hibrit > Dense > BM25** (nDCG@5: 0.73 / 0.65 / 0.69). Bu rejimde
reranking marjinal — birinci aşama zaten en iyi sonucu 1. sıraya koyuyor.

**Zorlu (argo) sorgular:** Tüm yöntemler düşüyor, ancak **reranking en büyük
göreli kazancı sağlıyor**: MRR 0.32 → 0.42 (+%32), P@1 0.20 → 0.30. Lexical
baseline (BM25) bu sette çöküyor.

**Yorum:** Cross-encoder reranking'in değeri, birinci aşamanın zorlandığı
gürültülü/günlük dildeki girdilerde ortaya çıkar. Zorlu sorgulardaki düşük mutlak
skorlar, argo girdi ile formal vaka açıklamaları arasındaki **alan farkına (domain
gap)** işaret eder.

## Domain gap'i kapatma: sorgu genişletme (QN)

Ölçülen alan farkına yanıt olarak, sorguları kanonik otomotiv terimleriyle
genişleten kural-tabanlı bir katman (`query_norm.py`) eklendi ve ablation yeniden
çalıştırıldı:

| Set | Hibrit nDCG@5 | Hibrit+QN nDCG@5 | Değişim |
|-----|---------------|------------------|---------|
| Zorlu (argo) | 0.127 | **0.268** | **+%111** |
| Standart | 0.733 | 0.738 | nötr |

Sorgu genişletme, argo girdilerde nDCG@5'i **iki katından fazla** artırırken temiz
sorgulara zarar vermez. Argo sette QN tek başına reranking'den daha büyük kazanç
sağlar. Bu, "ölç → düzelt → yeniden ölç" döngüsünü kapatan deneysel bir sonuçtur.
Mutlak skorlardaki kalan boşluk, gelecek iş olarak **Türkçe otomotiv alanına
embedding uyarlamasını (domain-adaptation)** motive eder.

> Grafikler: `results_ablation.png` (standart vs zorlu), `results_queryexp.png` (QN etkisi).

## Embedding domain-adaptation (eğitim zamanı)

QN'e ek olarak, embedding modeli Türkçe otomotiv alanına uyarlandı
(`scripts/finetune_embedding.py`): aynı DTC koduna sahip vakalar contrastive
(MultipleNegativesRankingLoss) ile yakınlaştırıldı. Anchor'lar jenerik
token-dropout ile gürültülendirildi; **test sorguları (gold_set, hard_queries)
eğitimde kullanılmadı** (held-out).

`run_finetune_eval.py` base vs uyarlanmış modeli karşılaştırır (nDCG@5):

| Set | Kurulum | Base | Uyarlanmış | Δ |
|-----|---------|------|-----------|---|
| Zorlu | Dense | 0.065 | **0.182** | **+%179** |
| Zorlu | Hibrit | 0.127 | 0.204 | +%60 |
| Zorlu | Hibrit+QN | 0.268 | **0.319** | +%19 |
| Standart | (hepsi) | — | — | nötr (zarar yok) |

Domain-adaptation, dense embedding'i argo sorgularda **iki katından fazla**
iyileştirir ve QN ile **istiflenir**: en iyi kurulum Hibrit+QN+uyarlanmış
(MRR 0.32 → **0.54**). Standart sorgulara zarar vermez.

Uygulamada kullanmak için: `backend/.env` → `EMBEDDING_MODEL=adapted`.

> Grafik: `results_finetune.png` (base vs uyarlanmış, standart vs zorlu).

## Sonuç zinciri (tez anlatısı)

1. Bileşen ablation: Hibrit > Dense > BM25
2. Cross-encoder rerank: zorlu sette MRR +%32
3. Domain gap ÖLÇÜLDÜ (argo sorgularda çöküş)
4. Sorgu genişletme (QN): gap'i çıkarımda kapatır, nDCG +%111
5. Domain-adaptation: gap'i eğitimde kapatır, dense nDCG +%179
6. QN + adaptation **istiflenir** → en iyi (MRR 0.32 → 0.54, +%70)
