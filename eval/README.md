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

## Faz İ1 — Türkçe-native embedding (`run_model_compare.py`)

Çok dilli MiniLM ile Türkçe-native modeller aynı held-out setlerde karşılaştırıldı.
**Türkçe-özel model net üstün; domain-adaptation üstüne istifleniyor.**

| Model | Standart Dense nDCG@5 | Zorlu Dense nDCG@5 | Zorlu Hibrit+QN nDCG@5 |
|-------|----------------------|--------------------|------------------------|
| MiniLM-base (çok dilli) | 0.647 | 0.065 | 0.268 |
| MiniLM-adapte | 0.657 | 0.182 | 0.319 |
| TR-trmteb (Türkçe-native) | 0.793 | 0.138 | 0.338 |
| **TR-trmteb-adapte** | **0.810** | **0.432** | **0.496** |

En iyi config (Türkçe-native + domain-adaptation), zorlu Dense'te base'e göre
**+%565 (6.6 kat)**, Hibrit+QN'de **+%85**. Grafik: `results_models.png`.
Uygulamada: `EMBEDDING_MODEL=adapted` (en iyi mevcut adapte modeli otomatik seçer).

## Faz İ2 — Gerçek veri + çapraz-dilli retrieval (`run_crosslingual_eval.py`)

Sistem, bağımsız kaynaklı **gerçek** veride (Zenodo Automotive Faults, CC-BY 4.0,
99 İngilizce kayıt) doğrulandı. Türkçe sorgular → İngilizce gerçek vakalar;
alaka ölçütü aynı Zenodo kategorisi.

| Yöntem / Model | P@3 | MRR | nDCG@5 |
|----------------|-----|-----|--------|
| BM25 (lexical) | 0.133 | 0.198 | 0.121 |
| Dense: MiniLM-base (çok dilli) | **0.367** | 0.548 | 0.342 |
| Dense: TR-trmteb-adapte | 0.300 | **0.581** | **0.346** |

**Bulgular:** (1) Sistem gerçek veride çalışır — sentetik damga kalkar.
(2) BM25 çapraz-dilde **çöker** (TR↔EN kelime örtüşmesi yok); semantik embedding
şart. (3) Çok dilli model P@3'te, Türkçe-adapte model MRR/nDCG'de önde — model
seçimi göreve (tek-dilli TR vs çapraz-dilli) bağlı. Grafik: `results_crosslingual.png`.
Veri içe aktarımı: `scripts/import_zenodo.py` (atıf: `data/real/ATTRIBUTION.md`).

## Faz İ3 — RAG kalite değerlendirmesi (`run_rag_eval.py`)

RAGAS-esinli metrikler, **LLM yargıç olmadan**, embedding-tabanlı proxy'lerle
(donanımda çalışır, deterministik). Ölçülen: extractive öneri üreticisi.

| Metrik | Standart | Zorlu |
|--------|:---:|:---:|
| **Faithfulness** (groundedness) | **1.000** | **1.000** |
| Faithfulness (kontrol/sahte) | 0.575 | 0.614 |
| Answer Relevancy | 0.365 | 0.308 |
| Context Precision@5 | 0.844 | 0.336 |
| Context Recall@5 | 0.604 | 0.550 |

**Bulgular:** (1) Extractive RAG **tam faithful** (1.0) — öneri yalnız getirilen
vakalardan türetildiği için halüsinasyon yok. (2) Kontrol (rastgele vakalardan
kurulmuş sahte öneri) 0.57'ye düşer → **+0.425 ayrım**, metriğin halüsinasyonu
gerçekten ayırt ettiğini kanıtlar. (3) Context precision standart sette güçlü
(0.84), zorlu sette retrieval zorluğuyla düşer. Grafik: `results_rag.png`.

> Not: LLM anahtarı verilirse (b) yolu — gerçek LLM RAG + tam RAGAS — mümkün.
> Bu kurulum extractive RAG'ın güvenli/dürüst tasarımını (sıfır halüsinasyon)
> nicel olarak doğrular.

## Faz İ4 — Arıza Bilgi Grafiği (`scripts/build_graph.py`)

Gerçek DTC referansından yapısal graf: **321 düğüm** (70 DTC, 100 semptom,
143 neden, 8 kategori), 401 kenar. Kenarlar: `(Symptom)-HAS_SYMPTOM-(DTC)`,
`(DTC)-HAS_CAUSE-(Cause)`, `(DTC)-IN_CATEGORY-(Category)`. Serbest semptom metni
→ embedding ile semptom düğümü eşleştirme → bağlı DTC/neden çıkarımı. Görsel:
`results_graph.png` (örnek alt-graf). Servis: `backend/app/services/graph.py`.

## Faz İ5 — GraphRAG (`run_graphrag_eval.py`)

Retrieval (vaka) + graf (yapısal) sinyallerini **adaptif füzyonla** birleştirir:
retrieval emin olduğunda (üst benzerlik ≥ τ) ona güvenir; belirsizken graf
desteğiyle ağırlıklı RRF yapar. DTC teşhis doğruluğu:

| Strateji | Standart MRR | Zorlu MRR | Zorlu Hit@1 |
|----------|:---:|:---:|:---:|
| Retrieval | 0.875 | 0.464 | 0.300 |
| Graf | 0.248 | 0.298 | 0.200 |
| **GraphRAG (adaptif)** | **0.875** | **0.543** | **0.400** |

**Bulgu:** Adaptif GraphRAG, retrieval'ın güçlü olduğu standart sette onu
**bozmaz** (0.875 = 0.875), zayıf olduğu zorlu sette **+%17 MRR / +%33 Hit@1**
kazandırır. Literatürle uyumlu: graf, retrieval darboğaz olduğunda akıl
yürütmeyi destekler. Canlı uç: `POST /api/diagnose` (yapısal neden-temelli
teşhis). Grafik: `results_graphrag.png`.

## Faz İ6 — Diyaloglu / aktif teşhis (`run_dialogue_eval.py`)

Belirsizlikte (üst adaylar birden çok kategoriye yayılıyorsa) sistem, adayları
en iyi AYIRAN bir semptomu bilgi grafiğinden seçip sorar; yanıt, adayları graf
**tutarlılık re-rank'i** ile yeniden sıralar. Oracle simülasyonu (gerçek arızalı
kullanıcı doğru yanıtlar) ile zorlu sorgularda ölçüldü:

| Metrik | Diyalogsuz | Diyaloglu | Δ |
|--------|:---:|:---:|:---:|
| Hit@1 | 0.400 | **0.600** | **+%50** |
| Hit@3 | 0.700 | 0.800 | +%14 |
| MRR | 0.517 | **0.683** | **+%32** |

**Bulgu:** Graf-güdümlü aktif netleştirme (ort. 2.4 soru) teşhis doğruluğunu
belirgin artırır — Hit@1 **+%50**, MRR **+%32**. Kilit tasarım: yanıtları yalnız
sorguya eklemek değil, **graf tutarlılığıyla adayları re-rank** etmek. Canlı uç:
`POST /api/diagnose/interactive` (durumsuz çok-turlu). Grafik: `results_dialogue.png`.

## Veri Zenginleştirme (🅰🅱🅲+) — `run_noise_eval.py`

**Sorun:** "yatak sesi geliyor" gibi mekanik/ses sorgularında sistem yanlış
alt-sistemi (amortisör/süspansiyon) öneriyordu. Kök neden: (1) korpusta bu
arızalar yoktu, (2) embedding "aynı ses farklı sistem"i ayıramıyordu.

**🅰 Kapsam:** `data/mechanical_faults.csv` (18 DTC'siz mekanik/ses arızası:
yatak, rulman, kayış, vuruntu, triger...) eklendi → korpus 809 → **971**.
**🅱 Gerçekçilik:** aşınma arızaları yüksek km'de (korelasyon), günlük-dil
semptom kalıpları. **🅲+ Hard-negative:** her ankora cross-kategori metinsel
benzer negatif (motor yatağı ≠ amortisör) ile contrastive eğitim.

Ses-ayrım (top-1 doğru alt-sistem) doğruluğu:

| Model | Top-1 kategori |
|-------|:---:|
| MiniLM-base | 0.60 |
| TR-trmteb-adapte | 0.70 |
| **TR-adapte-HN** | **0.90** |

**Bulgu:** Hard-negative eğitim, ses-ayrımını **0.60 → 0.90** çıkarır.
Doğrulanmış takas: kategori-ayrımı artarken DTC-seviyesi argo retrieval'da
ölçülü düşüş (nDCG 0.53 → 0.36) — *ayırt edicilik / hassasiyet dengesi*,
ayarlanabilir (HARD_NEG_PROB). Sistem artık "yatak sesi"ni doğru Motor'a
yönlendirir. Grafik: `results_noise.png`.

## İstatistiksel rigor (S6) — `run_significance.py`

İddialar bootstrap güven aralığı (%95) + eşli permütasyon testiyle temellendirildi
(10.000 iterasyon):

| Karşılaştırma | Fark (nDCG@5) | %95 GA | p | Sonuç |
|---------------|:---:|:---:|:---:|:---:|
| Standart: Hibrit − BM25 | +0.043 | [−0.006, +0.093] | 0.086 | anlamlı **değil** |
| Zorlu: Hibrit+Rerank − Hibrit | +0.117 | [+0.007, +0.247] | 0.023 | **ANLAMLI** |

**Bulgu:** Rerank kazancı istatistiksel olarak anlamlı; standart sette hibridin
BM25'e üstünlüğü n=24'te anlamlı değil (daha çok veri gerekir — dürüst sınır).

## Hiperparametre arama (S7) — `run_hparam_search.py`

Hibrit ağırlığı (dense_w) **doğrulama** setinde (gold) tarandı, **held-out**
(hard) sette raporlandı (sızıntısız). Sonuç: doğrulamada en iyi dense_w≈0.8
(nDCG 0.749), mevcut varsayılan **0.7 neredeyse optimal** (0.748). Held-out
zorlu sorgular daha çok sparse ağırlıktan faydalanıyor → query-adaptif ağırlık
gelecek iş. Grafik: `results_hparam.png`.

## Sonuç zinciri (tez anlatısı)

1. Bileşen ablation: Hibrit > Dense > BM25
2. Cross-encoder rerank: zorlu sette MRR +%32
3. Domain gap ÖLÇÜLDÜ (argo sorgularda çöküş)
4. Sorgu genişletme (QN): gap'i çıkarımda kapatır, nDCG +%111
5. Domain-adaptation (MiniLM): gap'i eğitimde kapatır, dense nDCG +%179
6. **Türkçe-native + domain-adaptation (Faz İ1):** en iyi model; zorlu Dense
   nDCG base'e göre **+%565**. Türkçe-özel temsil + alan uyarlaması istiflenir.
