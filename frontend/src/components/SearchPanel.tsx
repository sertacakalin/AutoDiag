import { useState } from "react";
import type { SearchOptions } from "../api/types";
import styles from "./SearchPanel.module.css";

interface Props {
  categories: string[];
  loading: boolean;
  onSearch: (query: string, opts: SearchOptions) => void;
  initialQuery?: string;
}

const TOP_K_OPTIONS = [3, 5, 8, 10];

export function SearchPanel({ categories, loading, onSearch, initialQuery = "" }: Props) {
  const [query, setQuery] = useState(initialQuery);
  const [category, setCategory] = useState("");
  const [dtc, setDtc] = useState("");
  const [topK, setTopK] = useState(5);
  const [useRag, setUseRag] = useState(true);

  const canSubmit = query.trim().length >= 3 && !loading;

  function submit() {
    if (!canSubmit) return;
    onSearch(query.trim(), {
      category: category || null,
      dtcCode: dtc.trim() || null,
      topK,
      useRag,
    });
  }

  // ⌘/Ctrl + Enter ile arama.
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  }

  return (
    <section className={styles.panel} aria-label="Arıza arama">
      <div className={styles.field}>
        <label htmlFor="query" className="eyebrow">
          Arıza tanımı
        </label>
        <textarea
          id="query"
          className={styles.textarea}
          placeholder="Belirtileri kendi cümlelerinizle yazın — örn. “Hızlanırken motor titriyor, gaz tepkisi azaldı ve arıza lambası yandı.”"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          rows={3}
          spellCheck={false}
        />
      </div>

      <div className={styles.toolbar}>
        <div className={styles.filters}>
          <label className={styles.control}>
            <span className={styles.controlLabel}>Kategori</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={styles.select}
            >
              <option value="">Tümü</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.control}>
            <span className={styles.controlLabel}>DTC kodu</span>
            <input
              value={dtc}
              onChange={(e) => setDtc(e.target.value.toUpperCase())}
              placeholder="P0300"
              className={styles.dtcInput}
              maxLength={8}
              spellCheck={false}
            />
          </label>

          <label className={styles.control}>
            <span className={styles.controlLabel}>Sonuç</span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className={styles.select}
            >
              {TOP_K_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n} kayıt
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            role="switch"
            aria-checked={useRag}
            className={styles.toggle}
            data-on={useRag}
            onClick={() => setUseRag((v) => !v)}
            title="Geçmiş vakalardan teşhis önerisi sentezle"
          >
            <span className={styles.toggleTrack}>
              <span className={styles.toggleThumb} />
            </span>
            Teşhis önerisi
          </button>
        </div>

        <div className={styles.actions}>
          <kbd className={styles.kbd}>⌘ ↵</kbd>
          <button
            type="button"
            className={styles.submit}
            onClick={submit}
            disabled={!canSubmit}
          >
            {loading ? "Aranıyor…" : "Ara"}
          </button>
        </div>
      </div>
    </section>
  );
}
