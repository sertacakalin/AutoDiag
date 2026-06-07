# Gerçek Veri Kaynakları — Atıf

Bu klasördeki gerçek veriler üçüncü taraf kaynaklardan alınmıştır ve ilgili
lisanslar uyarınca atıf gerektirir.

## Zenodo Automotive Faults Dataset

- **Eser:** Automotive Faults Dataset for Diagnostic and Maintenance Systems
- **Yazarlar:** Aktc, Obike et al. (Michael Okpara University of Agriculture;
  University of Uyo)
- **Kaynak:** Zenodo — https://zenodo.org/records/15626055
- **DOI:** 10.5281/zenodo.15626055
- **Lisans:** Creative Commons Attribution 4.0 International (CC-BY 4.0)
- **İçerik:** 99 yapısal otomotiv arıza kaydı (kategori, alt-kategori/bileşen,
  semptomlar, teşhis adımları), İngilizce.

**Kullanım:** `scripts/import_zenodo.py` ham JSON'u indirip AutoDiag şemasına
çevirir (`zenodo_faults.csv`). Faz İ2'de çapraz-dilli retrieval değerlendirmesinde
(Türkçe sorgu → İngilizce gerçek vaka) kullanılır.

> CC-BY 4.0 uyarınca eser sahiplerine atıf yapılmıştır. Ham veri yeniden
> dağıtılmaz; betikle indirilir. Türetilmiş CSV, dönüşüm ürünüdür ve `source`
> sütununda kaynağı taşır.

## NHTSA ODI Complaints

- **Eser:** NHTSA Office of Defects Investigation (ODI) — Vehicle Complaints
- **Kaynak:** ABD Ulusal Karayolu Trafik Güvenliği İdaresi —
  https://www.nhtsa.gov/nhtsa-datasets-and-apis
- **API:** https://api.nhtsa.gov/complaints/complaintsByVehicle
- **Lisans:** ABD federal kamu malı (public domain) — kısıtsız kullanım
- **İçerik:** Gerçek sürücü arıza şikayetleri (doğal-dil belirti metni,
  araç marka/model/yıl, bileşen), İngilizce. 8 AutoDiag kategorisine eşlenen
  3164 kayıt çekildi (`nhtsa_faults.csv`).

**Kullanım:** `scripts/import_nhtsa.py` resmi JSON API'den (scraping yok,
rate-limitli) şikayetleri çeker, AutoDiag şemasına eşler. Ayrı bir İngilizce /
çapraz-dilli katman olarak tutulur (Türkçe eğitim korpusuna karıştırılmaz —
karıştırmanın Türkçe-argo performansını seyrelttiği `eval/run_data_compare.py`
ile ölçüldü). `solution`/`dtc_code` NHTSA'da yoktur, boştur.

> Kamu malı olduğundan lisans kısıtı yoktur; yine de kaynak şeffaflık için
> belgelenmiştir. Kişisel veri (VIN vb.) içe aktarımda dışlanır.
