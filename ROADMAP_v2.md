# AutoDiag — İleri Seviye Yol Haritası (v2)

Temel sistem (Faz 0–12) tamamlandı: iki aşamalı hibrit retrieval + cross-encoder
rerank + sorgu genişletme + domain-adapte embedding + RAG + ablation. Bu belge,
projeyi **güçlü bir tez / yayınlanabilir araştırma** seviyesine taşıyan ileri
fazları tanımlar. Her faz **ölçülebilir** bir çıktı üretir ve ablation ile
"önce/sonra" kanıtlanır.

> İlke: her faz bir öncekine dayanır; her faz doğrulanmadan ilerleme.

---

## Faz İ1 — Türkçe-native embedding

**Amaç:** Çok dilli MiniLM yerine Türkçe-özel embedding modeli değerlendirmek.
**Yaklaşım:** TurkEmbed / BERTurk-contrastive / `trmteb/turkish-embedding-model`
gibi Türkçe modelleri, base-MiniLM ve domain-adapte MiniLM ile aynı held-out
setlerde karşılaştır.
**Çıktı:** `eval/run_model_compare.py` + karşılaştırma grafiği; kazanan model.
**Kabul:** Türkçe model, argo sorgularda base'i geçer (nDCG@5/MRR).

## Faz İ2 — Gerçek veri entegrasyonu

**Amaç:** Sentetik damgayı kaldırmak; kredibilite + ölçek.
**Yaklaşım:** Zenodo Automotive Faults (CC-BY, İngilizce) gerçek vaka kümesini
içe aktar; küçük gerçek Türkçe doğrulama seti oluştur. Çapraz-dilli transfer
ölç ("İngilizce gerçek veri ↔ Türkçe sorgu").
**Çıktı:** `data/real/` + içe aktarıcı + gerçek-veri eval raporu.
**Kabul:** Sistem gerçek veride çalışır; sonuçlar raporlanır.

## Faz İ3 — RAG kalitesi değerlendirmesi (RAGAS)

**Amaç:** Sadece retrieval'ı değil, **öneri kalitesini/halüsinasyonu** ölçmek.
**Yaklaşım:** RAGAS metrikleri — faithfulness (vakalara sadakat), answer
relevancy, context precision. LLM yargıç yoksa hafif/lokal proxy uygula.
**Çıktı:** `eval/run_rag_eval.py` + RAG kalite tablosu.
**Kabul:** Faithfulness ve context precision raporlanır; halüsinasyon ölçülür.

## Faz İ4 — Arıza Bilgi Grafiği (Knowledge Graph)

**Amaç:** Yapısal akıl yürütme için neden-sonuç grafiği.
**Yaklaşım:** Semptom → bileşen → neden → DTC → çözüm düğümleri; DTC referansı +
vakalardan otomatik çıkarım. NetworkX ile graf; sorgu → ilgili alt-graf.
**Çıktı:** `backend/app/services/graph.py` + graf inşa scripti + görselleştirme.
**Kabul:** Bir semptomdan olası neden/çözüm yolları çıkarılabiliyor.

## Faz İ5 — GraphRAG (graf-temelli RAG)

**Amaç:** SOTA: öneriyi yapısal neden-sonuç yollarına dayandır → halüsinasyon ↓.
**Yaklaşım:** Retrieval + ilgili KG alt-grafını RAG bağlamına ekle; vanilla RAG
ile karşılaştır (RAGAS faithfulness).
**Çıktı:** GraphRAG hattı + karşılaştırma.
**Kabul:** GraphRAG, vanilla RAG'a göre faithfulness'ta kazanır.

## Faz İ6 — Diyaloglu / aktif teşhis (opsiyonel)

**Amaç:** Arama kutusunu teşhis asistanına çevirmek.
**Yaklaşım:** Belirsizlikte netleştirici soru üret (eksik bilgi aktif sorgulama);
çok turlu oturum durumu.
**Çıktı:** Diyalog uç noktası + arayüz akışı.
**Kabul:** Sistem eksik bilgi için soru sorup teşhisi daraltır.

---

## Değerlendirme omurgası (her fazda)

Mevcut: P@1/3/5, MRR, nDCG@5 (retrieval) + ablation (standart vs zorlu).
Eklenecek: RAGAS (faithfulness, answer relevancy, context precision) — RAG katmanı.

## Sınırlama takibi

Her faz, `eval/README.md` ve kök `README.md`'deki bulgu/sınırlama bölümlerini
günceller. Dürüst çerçeve korunur: sistem teşhis koymaz, destekler.
