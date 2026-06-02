// Küçük, tekrar kullanılan görsel parçacıklar.
import type { Confidence } from "../../api/types";
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

const CONFIDENCE_LABEL: Record<Confidence, string> = {
  yüksek: "Yüksek güven",
  orta: "Orta güven",
  düşük: "Düşük güven",
};

/** Teşhis önerisi güven rozeti. */
export function ConfidenceBadge({ level }: { level: Confidence }) {
  return (
    <span className={styles.confidence} data-level={level}>
      <span className={styles.confDot} aria-hidden />
      {CONFIDENCE_LABEL[level]}
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

/** Benzerlik/alaka göstergesi — yatay ölçek çubuğu + yüzde. */
export function SimilarityMeter({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  // Eşik bandı: yüksek/orta/düşük alaka — çubuğun rengini belirler.
  const band = pct >= 75 ? "high" : pct >= 50 ? "mid" : "low";
  return (
    <div className={styles.meter} title={`Alaka: %${pct}`}>
      <div className={styles.meterTrack}>
        <div
          className={styles.meterFill}
          data-band={band}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={styles.meterValue} data-band={band}>
        %{pct}
      </span>
    </div>
  );
}
