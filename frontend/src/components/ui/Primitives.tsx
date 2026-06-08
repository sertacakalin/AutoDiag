// Küçük, tekrar kullanılan görsel parçacıklar.
import styles from "./Primitives.module.css";

/** DTC arıza kodu — daima monospace, teknik rozet. */
export function DtcCode({ code }: { code: string | null }) {
  if (!code) return null;
  return <span className={styles.dtc}>{code}</span>;
}

/** Kategori etiketi (renk noktası + ad). */
export function CategoryTag({ name }: { name: string }) {
  return (
    <span className={styles.category}>
      <span className={styles.dot} data-cat={name} aria-hidden />
      {name}
    </span>
  );
}

/** Arıza önem derecesi rozeti (Düşük / Orta / Yüksek / Kritik). */
export function SeverityBadge({ level }: { level: string }) {
  if (!level) return null;
  return (
    <span className={styles.severity} data-level={level}>
      {level}
    </span>
  );
}

/**
 * Benzerlik/alaka göstergesi — yatay ölçek çubuğu + bandlı etiket.
 *
 * Ham skor (rerank güveni) sigmoid çıktısı olduğu için tepe noktada doygunlaşır:
 * çok alakalı iki vaka da 0.99+'a sıkışır ve yuvarlanınca ikisi de "%100" görünür
 * → "kusursuz eşleşme" yanılgısı. Bunun yerine alakayı bantlara ayırıp sözel
 * etiket gösteriyoruz; ham yüzde yalnızca tooltip'te (teknisyen için) kalıyor.
 */
const SIM_BANDS = [
  { min: 0.85, band: "high", label: "Çok yüksek alaka" },
  { min: 0.65, band: "high", label: "Yüksek alaka" },
  { min: 0.45, band: "mid", label: "Orta alaka" },
  { min: 0, band: "low", label: "Düşük alaka" },
] as const;

export function SimilarityMeter({ value }: { value: number }) {
  const v = Math.max(0, Math.min(1, value));
  const pct = Math.round(v * 100);
  const { band, label } = SIM_BANDS.find((b) => v >= b.min) ?? SIM_BANDS[SIM_BANDS.length - 1];
  return (
    <div className={styles.meter} title={`Alaka skoru: %${pct}`}>
      <div className={styles.meterTrack}>
        <div className={styles.meterFill} data-band={band} style={{ width: `${pct}%` }} />
      </div>
      <span className={styles.meterLabel} data-band={band}>
        {label}
      </span>
    </div>
  );
}
