import { useState } from "react";
import type { SearchHit } from "../api/types";
import { CategoryTag, DtcCode, SimilarityMeter } from "./ui/Primitives";
import styles from "./ResultList.module.css";

interface Props {
  hits: SearchHit[];
  onFeedback: (hit: SearchHit, helpful: boolean) => void;
}

export function ResultList({ hits, onFeedback }: Props) {
  return (
    <ol className={styles.list}>
      {hits.map((hit, i) => (
        <ResultCard key={hit.fault_id} hit={hit} rank={i + 1} onFeedback={onFeedback} />
      ))}
    </ol>
  );
}

function ResultCard({
  hit,
  rank,
  onFeedback,
}: {
  hit: SearchHit;
  rank: number;
  onFeedback: (hit: SearchHit, helpful: boolean) => void;
}) {
  const [voted, setVoted] = useState<null | boolean>(null);

  function vote(helpful: boolean) {
    if (voted !== null) return;
    setVoted(helpful);
    onFeedback(hit, helpful);
  }

  const meta = [
    hit.vehicle_model,
    hit.mileage_km != null ? `${hit.mileage_km.toLocaleString("tr-TR")} km` : null,
  ].filter(Boolean) as string[];

  return (
    <li className={styles.card}>
      <header className={styles.head}>
        <span className={styles.rank}>#{rank}</span>
        <SimilarityMeter value={hit.similarity} />
        <div className={styles.tags}>
          <CategoryTag name={hit.category} />
          <DtcCode code={hit.dtc_code} />
        </div>
      </header>

      <p className={styles.desc}>{hit.description}</p>

      <div className={styles.solution}>
        <span className="eyebrow">Uygulanan çözüm</span>
        <p>{hit.solution}</p>
      </div>

      <footer className={styles.foot}>
        {meta.length > 0 && <span className={styles.vehicle}>{meta.join(" · ")}</span>}
        <div className={styles.feedback}>
          {voted === null ? (
            <>
              <span className={styles.fbLabel}>Bu vaka yardımcı oldu mu?</span>
              <button className={styles.fbBtn} onClick={() => vote(true)} data-kind="yes">
                Faydalı
              </button>
              <button className={styles.fbBtn} onClick={() => vote(false)} data-kind="no">
                Değil
              </button>
            </>
          ) : (
            <span className={styles.fbDone} data-helpful={voted}>
              {voted ? "Geri bildiriminiz kaydedildi" : "Geri bildirim alındı"}
            </span>
          )}
        </div>
      </footer>
    </li>
  );
}
