# AutoDiag — Jüri Demo Soruları

Aşağıdaki sorular gerçek sistemde (1514 kayıt, hibrit arama + cross-encoder
yeniden sıralama) test edildi. Skorlar **gerçek ölçümlerdir**. Bilinçli olarak
hep %100 çıkmayan, bazıları birden çok kategoride rekabet eden sorular seçildi —
amaç sistemin *dürüst* ve *gerçekçi* davrandığını göstermek.

> Not: Sonuçlar geçmiş vakalara dayalı **karar destek**tir, kesin teşhis değildir.
> Bunu jüriye baştan söylemek güven verir.

---

## 1) Argo/günlük dil → kanonik genişletme (güçlü isabet)

**Soru:** `direksiyon zor dönüyor`
Sistem sorguyu otomatik genişletir → *"ağırlaşma sertleşme"*

| Skor | Kategori | Vaka |
|------|----------|------|
| %99.9 | Direksiyon | Direksiyon ağırlaştı, manevrada zor dönüyor |
| %99.3 | Direksiyon | Direksiyonu çevirmek zor, dönüşlerde sertlik |
| %94.8 | Direksiyon | Park ederken direksiyon çok sert dönüyor |

**Jüriye:** "Kullanıcı teknik terim bilmek zorunda değil; günlük dili kanonik
arıza terimlerine genişletiyoruz."

---

## 2) Orta güven — dürüst sonuç (%80 civarı)

**Soru:** `gaza basınca araba tekliyor`
Genişletme → *"tekleme güç kaybı"*

| Skor | Kategori | Vaka |
|------|----------|------|
| %80.5 | Motor | Gaz verince araç sarsılıyor, ivmelenmede güç kaybı |
| %37.1 | Motor | Gaza basınca ıslık/siren sesi, ara sıra güç kaybı |
| %35.4 | Motor | Rampada kalkışta güç dalgalanması |

**Jüriye:** "Burada en iyi eşleşme %80 — sistem emin olmadığında bunu skorla
şeffafça gösteriyor, sahte %100 üretmiyor."

---

## 3) Rakip kategoriler — birden fazla makul aday (çelişkili)

**Soru:** `araç sağa çekiyor`

| Skor | Kategori | Vaka |
|------|----------|------|
| %98.4 | Direksiyon | Araç sürekli sağa çekiyor |
| %98.3 | Süspansiyon | Araç yolda sağa sola yalpalıyor |
| %95.5 | Süspansiyon | Bir yay çökmüş, araç sağa yatık |

**Jüriye:** "Aynı belirti iki sistemi işaret edebilir (rot ayarı VS süspansiyon).
Sistem ikisini de yakın skorla sunuyor — teknisyene karar bırakıyor."

---

## 4) Aynı belirti farklı sistemlerde — sınıflandırma zorluğu

**Soru:** `fren yaparken tıkırtı sesi geliyor`

| Skor | Kategori | Vaka |
|------|----------|------|
| %99.9 | Motor | Fren yaparken soğukta tıkırtı |
| %99.7 | Süspansiyon | Ön taraftan tıkırtı/gümbürtü |
| %98.3 | Fren | Fren yaparken cıyak/gıcırtı |

**Jüriye:** "'Tıkırtı' birçok parçada olur. Sistem tek bir cevaba sıkışmıyor,
en olası 3 vakayı listeliyor — gerçek atölye mantığı bu."

---

## 5) Keskin ayrım — yüksek güven + net eleme

**Soru:** `akü sürekli bitiyor sabah çalışmıyor`
Genişletme → *"zor çalışma marş"*

| Skor | Kategori | Vaka |
|------|----------|------|
| %99.5 | Elektrik | Sabah akü bitmiş oluyor, sürekli takviye |
| %1.9 | Elektrik | Sinyaller hızlı yanıp sönüyor (alakasız) |
| %1.8 | Motor | Zor çalışma (zayıf eşleşme) |

**Jüriye:** "Emin olduğunda %99, alakasızı %2'ye düşürüyor — gürültüyü eliyor."

---

## 6) Otomatik şanzıman — net teşhis

**Soru:** `vites geçmiyor sertçe atıyor`

| Skor | Kategori | Vaka |
|------|----------|------|
| %98.0 | Şanzıman | Otomatik şanzıman geçişlerde sertçe vuruyor |
| %11.5 | Şanzıman | Manuel viteste debriyaj kaçırıyor |
| %10.9 | Elektrik | Gösterge ibreleri atıyor (alakasız) |

---

## Demo akış önerisi (3-4 dk)

1. **Soru 1** ile başla → argo genişletme + güçlü isabet (etkileyici giriş).
2. **Soru 2** → "%80, çünkü emin değil" (dürüstlük vurgusu).
3. **Soru 3 veya 4** → rakip kategoriler (sistemin karar-destek doğası).
4. **Soru 5** → keskin eleme (gürültü filtreleme).
5. Kapanış: "Bu bir teşhis *aracı* değil, teknisyene en benzer geçmiş vakaları
   ve uygulanmış çözümleri saniyede getiren bir *karar destek* sistemi."

> Sorular `localhost:8080` arayüzünde canlı çalıştırılabilir. Skorlar
> donanım/model durumuna göre ±birkaç puan oynayabilir.
