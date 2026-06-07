import type { RagSuggestion } from "../api/types";
import { ConfidenceBadge } from "./ui/Primitives";
import styles from "./SuggestionCard.module.css";

interface Props {
  suggestion: RagSuggestion;
  resultCount: number;
  ragSource?: "llm" | "extractive";
}

export function SuggestionCard({ suggestion, resultCount, ragSource }: Props) {
  return (
    <aside className={styles.card} aria-label="Teşhis önerisi">
      <header className={styles.head}>
        <div>
          <span className="eyebrow">Teşhis önerisi</span>
          <p className={styles.subtitle}>
            {resultCount} benzer vakadan sentezlendi
            {ragSource === "llm" ? (
              <span className={styles.source} data-kind="llm">🤖 Yapay zeka (yerel)</span>
            ) : ragSource === "extractive" ? (
              <span className={styles.source} data-kind="extractive">vakalardan çıkarım</span>
            ) : null}
          </p>
        </div>
        <ConfidenceBadge level={suggestion.confidence} />
      </header>

      <div className={styles.cause}>
        <span className="eyebrow">Olası neden</span>
        <p>{suggestion.likely_cause}</p>
      </div>

      {suggestion.recommended_steps.length > 0 && (
        <div className={styles.steps}>
          <span className="eyebrow">Önerilen adımlar</span>
          <ol>
            {suggestion.recommended_steps.map((step, i) => (
              <li key={i}>
                <span className={styles.stepNo}>{i + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className={styles.disclaimer}>
        Öneri yalnızca geçmiş kayıtlara dayanır. Nihai teşhis ve müdahale
        kararı yetkili teknisyene aittir.
      </p>
    </aside>
  );
}
