import styles from "./EmptyState.module.css";

const EXAMPLES = [
  "Hızlanırken motor titriyor ve arıza lambası yandı",
  "Frene basınca direksiyon ve pedal titriyor",
  "Vites geçişlerinde sarsıntı ve gecikme var",
  "Rölantide motor tekliyor, zaman zaman stop ediyor",
  "Klima soğutmuyor ama fan çalışıyor",
];

interface Props {
  onPick: (query: string) => void;
}

export function EmptyState({ onPick }: Props) {
  return (
    <div className={styles.wrap}>
      <div className={styles.mark} aria-hidden>
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
          <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
          <path
            d="m16.5 16.5 4 4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <h2 className={styles.title}>Arıza belirtilerini tanımlayın</h2>
      <p className={styles.lead}>
        Sistem, 152 çözülmüş vakadan oluşan bilgi tabanında hibrit arama yapar;
        en benzer kayıtları ve uygulanmış çözümleri listeler.
      </p>

      <div className={styles.examples}>
        <span className="eyebrow">Örnek sorgular</span>
        <div className={styles.chips}>
          {EXAMPLES.map((ex) => (
            <button key={ex} className={styles.chip} onClick={() => onPick(ex)}>
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
