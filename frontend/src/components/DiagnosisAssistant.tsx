import { useState } from "react";

import { ApiError, diagnoseInteractive } from "../api/client";
import type { GraphDiagnosis, InteractiveDiagnoseResponse } from "../api/types";
import { CategoryTag, DtcCode, SeverityBadge } from "./ui/Primitives";
import styles from "./DiagnosisAssistant.module.css";

type Phase = "idle" | "asking" | "final";

interface Turn {
  symptom: string;
  answer: boolean;
}

export function DiagnosisAssistant() {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [denied, setDenied] = useState<string[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState<{ q: string; symptom: string } | null>(null);
  const [diagnoses, setDiagnoses] = useState<GraphDiagnosis[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function apply(res: InteractiveDiagnoseResponse) {
    if (res.status === "question" && res.question && res.symptom) {
      setQuestion({ q: res.question, symptom: res.symptom });
      setPhase("asking");
    } else {
      setDiagnoses(res.diagnoses);
      setQuestion(null);
      setPhase("final");
    }
  }

  async function call(nextConfirmed: string[], nextDenied: string[]) {
    setLoading(true);
    setError(null);
    try {
      apply(await diagnoseInteractive(query.trim(), nextConfirmed, nextDenied));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Teşhis başlatılamadı.");
    } finally {
      setLoading(false);
    }
  }

  function start() {
    if (query.trim().length < 3 || loading) return;
    setConfirmed([]);
    setDenied([]);
    setTurns([]);
    setDiagnoses([]);
    void call([], []);
  }

  function answer(yes: boolean) {
    if (!question || loading) return;
    const nextConfirmed = yes ? [...confirmed, question.symptom] : confirmed;
    const nextDenied = yes ? denied : [...denied, question.symptom];
    setConfirmed(nextConfirmed);
    setDenied(nextDenied);
    setTurns([...turns, { symptom: question.symptom, answer: yes }]);
    void call(nextConfirmed, nextDenied);
  }

  function reset() {
    setPhase("idle");
    setQuestion(null);
    setDiagnoses([]);
    setTurns([]);
    setConfirmed([]);
    setDenied([]);
    setError(null);
  }

  return (
    <section className={styles.wrap}>
      <div className={styles.intro}>
        <span className="eyebrow">Teşhis asistanı · GraphRAG + aktif diyalog</span>
        <p>
          Arızayı tarif edin; sistem bilgi grafiği üzerinden olası nedenleri
          daraltmak için netleştirici sorular sorar.
        </p>
      </div>

      {phase === "idle" && (
        <div className={styles.starter}>
          <textarea
            className={styles.input}
            rows={2}
            placeholder="Örn. “araç titriyor ve gösterge panelinde uyarı var”"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") start();
            }}
            spellCheck={false}
          />
          <button className={styles.primary} onClick={start} disabled={query.trim().length < 3 || loading}>
            {loading ? "Başlatılıyor…" : "Teşhise başla"}
          </button>
        </div>
      )}

      {phase !== "idle" && (
        <div className={styles.session}>
          <div className={styles.queryLine}>
            <span className={styles.queryLabel}>Arıza:</span> {query}
          </div>

          {turns.length > 0 && (
            <div className={styles.transcript}>
              {turns.map((t, i) => (
                <span key={i} className={styles.turnChip} data-yes={t.answer}>
                  <span className={styles.turnMark}>{t.answer ? "✓" : "✕"}</span>
                  {t.symptom}
                </span>
              ))}
            </div>
          )}

          {error && <p className={styles.error}>{error}</p>}

          {phase === "asking" && question && (
            <div className={styles.question}>
              <p className={styles.questionText}>{question.q}</p>
              <div className={styles.answers}>
                <button className={styles.yes} onClick={() => answer(true)} disabled={loading}>
                  Evet, var
                </button>
                <button className={styles.no} onClick={() => answer(false)} disabled={loading}>
                  Hayır, yok
                </button>
              </div>
            </div>
          )}

          {phase === "final" && (
            <div className={styles.result}>
              <span className="eyebrow">Olası teşhisler (graf-temelli)</span>
              {diagnoses.length === 0 ? (
                <p className={styles.empty}>Eşleşen yapısal teşhis bulunamadı.</p>
              ) : (
                <ol className={styles.diagList}>
                  {diagnoses.map((d, i) => (
                    <DiagnosisCard key={d.dtc_code + i} d={d} rank={i + 1} />
                  ))}
                </ol>
              )}
              <button className={styles.restart} onClick={reset}>
                Yeni teşhis
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function DiagnosisCard({ d, rank }: { d: GraphDiagnosis; rank: number }) {
  return (
    <li className={styles.diag}>
      <div className={styles.diagHead}>
        <span className={styles.rank}>#{rank}</span>
        <DtcCode code={d.dtc_code} />
        <span className={styles.diagTitle}>{d.title}</span>
        <div className={styles.diagMeta}>
          <CategoryTag name={d.category} />
          <SeverityBadge level={d.severity} />
        </div>
      </div>
      {d.causes.length > 0 && (
        <div className={styles.causes}>
          <span className="eyebrow">Olası nedenler</span>
          <ul>
            {d.causes.slice(0, 5).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}
