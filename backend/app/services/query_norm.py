"""Sorgu anlama katmanı: Türkçe otomotiv argosunu kanonik terimlerle genişletir.

Sürücü/müşteri dili ("kızıyor", "taş gibi", "zıp zıp") ile teknik kayıt dili
("aşırı ısınma", "direksiyon ağırlaşması", "titreşim") arasında bir alan farkı
(domain gap) vardır. Ablation bu farkı ölçtü (argo sorgularda tüm yöntemler
düşüyor). Bu katman, sorguya kanonik eşanlamlıları EKLEYEREK (replace değil,
expand) hem sparse (BM25 anahtar kelime örtüşmesi) hem dense (daha net semantik)
sinyalini güçlendirir.

Tasarım ilkeleri:
  - Deterministik ve AÇIKLANABİLİR (kural-tabanlı; teşhis aracında şeffaflık şart).
  - Genel otomotiv argosu — belirli test sorgularına göre değil, alan bilgisine göre.
  - Orijinal sözcükler korunur; yalnız kanonik terimler eklenir (geri-uyumlu).
"""

from __future__ import annotations

import re

# (tetikleyici ifadeler, eklenecek kanonik terimler)
# Tetikleyiciler normalize edilmiş (küçük harf) metinde alt-dizi olarak aranır.
LEXICON: list[tuple[tuple[str, ...], str]] = [
    # Aşırı ısınma / sıcaklık
    (("kızıyor", "kaynıyor", "fokurdu", "çok ısın", "aşırı ısın"), "hararet aşırı ısınma"),
    (("ibre kırmızı", "gösterge kırmızı", "kırmızıya"), "sıcaklık göstergesi hararet"),
    (("buhar", "tütüyor", "duman çıkıyor"), "buhar"),
    # Titreşim / sarsıntı / tekleme
    (("titri", "titreş", "zıp zıp", "zıplı", "sarsıl", "salla", "silki", "sallan"), "titreme titreşim sarsıntı"),
    (("tekli", "teklem", "boğul"), "tekleme güç kaybı"),
    # Güç / ivmelenme / şanzıman
    (("çekmiyor", "güç yok", "gitmiyor", "ileri git", "yağ gibi"), "güç kaybı ivmelenme"),
    (("devir fırlı", "devir yüksel", "devir artı", "rölantide gez"), "kavrama kayması devir yükseliyor"),
    # Çalıştırma / stop
    (("çalışmıyor", "uyanmı", "zor çalış", "geç tut", "marş bas", "marşa bas", "zor uyan"), "zor çalışma marş"),
    (("stop edi", "kendini bırak", "stop ed", "duruyor gibi", "söndü"), "stop ediyor rölanti"),
    # Elektrik / şarj
    (("akü ışığı", "akü işareti", "şarj ışığı", "kontak ışığı"), "akü şarj uyarısı voltaj"),
    (("far kısıl", "ışık sön", "farlar kıs", "kısılıp parlı"), "voltaj düşük aydınlatma"),
    # Sesler
    (("tıkırtı", "takırtı", "tıkır", "takır"), "tıkırtı ses"),
    (("gıcırtı", "cızırtı", "gıcır"), "gıcırtı ses"),
    (("vınla", "uğultu", "uğul"), "uğultu ses"),
    # Fren
    (("fren tutmu", "pedal sert", "pedal boşal", "fren boşal"), "fren pedal"),
    (("abs ışığı", "abs uyar", "abs yan"), "ABS uyarı"),
    # Direksiyon
    (("taş gibi", "kaskatı", "direksiyon ağır", "zor dönüy", "ağırlaş"), "direksiyon ağırlaşma sertleşme"),
    (("direksiyon boş", "direksiyon oyn", "boşluk var"), "direksiyon boşluk"),
    # Klima
    (("soğutmu", "ılık üfl", "sıcak hava", "üflemi", "serinletmi"), "klima soğutmuyor"),
    # Egzoz / emisyon / uyarı lambası
    (("muayene", "egzoz test", "emisyon test"), "egzoz emisyon"),
    (("sarı lamba", "motor ışığı", "arıza lamba", "check engine", "ikaz lamba"), "arıza lambası motor uyarı"),
    (("siyah duman", "is atı", "is yapı"), "siyah duman zengin karışım"),
    # Yakıt / tüketim
    (("çok yakı", "yakıt arttı", "sarfiyat", "benzin bitiyor", "fazla yakı"), "yüksek yakıt tüketimi"),
]

_WHITESPACE_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.lower()).strip()


def expand_query(query: str) -> str:
    """Sorguyu kanonik otomotiv terimleriyle genişlet (orijinali koruyarak).

    Hiç eşleşme yoksa sorgu olduğu gibi döner.
    """
    low = _norm(query)
    additions: list[str] = []
    seen: set[str] = set()
    for triggers, canonical in LEXICON:
        if any(t in low for t in triggers):
            for term in canonical.split():
                key = term.lower()
                # Zaten sorguda/eklenenlerde yoksa ekle.
                if key not in seen and key not in low:
                    seen.add(key)
                    additions.append(term)
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"


def was_expanded(query: str) -> bool:
    """Sorgu genişletmeye konu oldu mu (UI/gözlem için)."""
    return expand_query(query) != query
