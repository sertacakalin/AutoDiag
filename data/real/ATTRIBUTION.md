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
