import { useCallback, useEffect, useState } from "react";

import { ApiError, health, search, sendFeedback, UnauthorizedError } from "./api/client";
import type { HealthResponse, SearchHit, SearchOptions, SearchResponse, User } from "./api/types";
import { useAuth } from "./auth/AuthContext";
import { AddFaultDrawer } from "./components/AddFaultDrawer";
import { DiagnosisAssistant } from "./components/DiagnosisAssistant";
import { EmptyState } from "./components/EmptyState";
import { LoginScreen } from "./components/LoginScreen";
import { ResultList } from "./components/ResultList";
import { SearchPanel } from "./components/SearchPanel";
import { SuggestionCard } from "./components/SuggestionCard";
import { Toast, type ToastState } from "./components/Toast";
import styles from "./App.module.css";

export function App() {
  const { isAuthenticated, loading: authLoading } = useAuth();

  // Açılış oturum doğrulaması sürerken kısa bir bekleme ekranı göster.
  if (authLoading) {
    return (
      <div className={styles.app}>
        <div className={styles.bootSplash} role="status" aria-live="polite">
          Oturum doğrulanıyor…
        </div>
      </div>
    );
  }

  // Oturum yoksa giriş ekranını göster; mevcut uygulama gizli kalır.
  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  return <Workspace />;
}

function Workspace() {
  const { user, logout } = useAuth();
  const [info, setInfo] = useState<HealthResponse | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [mode, setMode] = useState<"search" | "assistant">("search");

  // Örnek sorgu seçilince paneli tohumlamak için (key ile yeniden bağlanır).
  const [seed, setSeed] = useState<{ query: string; nonce: number }>({
    query: "",
    nonce: 0,
  });

  useEffect(() => {
    health()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  const runSearch = useCallback(
    async (query: string, opts: SearchOptions) => {
      setLoading(true);
      setError(null);
      try {
        const res = await search(query, opts);
        setResponse(res);
      } catch (e) {
        // Jeton geçersizleştiyse oturumu kapat ve giriş ekranına dön.
        if (e instanceof UnauthorizedError) {
          logout();
          return;
        }
        setError(e instanceof ApiError ? e.message : "Beklenmeyen bir hata oluştu.");
        setResponse(null);
      } finally {
        setLoading(false);
      }
    },
    [logout],
  );

  function pickExample(query: string) {
    setSeed({ query, nonce: seed.nonce + 1 });
    void runSearch(query, { topK: 5, useRag: true });
  }

  async function handleFeedback(hit: SearchHit, helpful: boolean) {
    if (!response) return;
    try {
      await sendFeedback({
        query_text: response.query,
        returned_fault_id: hit.fault_id,
        was_helpful: helpful,
      });
      setToast({ message: "Geri bildiriminiz kaydedildi.", kind: "success" });
    } catch {
      setToast({ message: "Geri bildirim gönderilemedi.", kind: "error" });
    }
  }

  const categories = info?.categories ?? [];

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brand}>
            <span className={styles.logo} aria-hidden>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M4 13a8 8 0 0 1 16 0"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <path
                  d="M12 13 15.5 9.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="13" r="1.6" fill="currentColor" />
              </svg>
            </span>
            <div className={styles.wordmark}>
              <strong>AutoDiag</strong>
              <span>Arıza Teşhis Destek Sistemi</span>
            </div>
          </div>

          <div className={styles.headerActions}>
            <SystemStatus info={info} />
            <button className={styles.addBtn} onClick={() => setDrawerOpen(true)}>
              <span aria-hidden>+</span> Kayıt ekle
            </button>
            <UserMenu user={user} onLogout={logout} />
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.tabs} role="tablist">
          <button
            className={styles.tab}
            data-active={mode === "search"}
            onClick={() => setMode("search")}
          >
            Vaka Arama
          </button>
          <button
            className={styles.tab}
            data-active={mode === "assistant"}
            onClick={() => setMode("assistant")}
          >
            Teşhis Asistanı
          </button>
        </div>

        {mode === "assistant" && <DiagnosisAssistant />}

        {mode === "search" && (
          <>
            <SearchPanel
              key={seed.nonce}
              categories={categories}
              loading={loading}
              onSearch={runSearch}
              initialQuery={seed.query}
            />

        <div className={styles.results}>
          {error && (
            <div className={styles.error} role="alert">
              <strong>Arama başarısız.</strong> {error}
            </div>
          )}

          {loading && <ResultsSkeleton />}

          {!loading && !error && response && response.results.length > 0 && (
            <div className={styles.grid}>
              <div>
                <div className={styles.resultsHead}>
                  <span className="eyebrow">
                    {response.results.length} sonuç · “{response.query}”
                  </span>
                  <div className={styles.badges}>
                    {response.reranked && (
                      <span
                        className={styles.rerankBadge}
                        title="Cross-encoder ile yeniden sıralandı (iki aşamalı arama)"
                      >
                        2 aşamalı · yeniden sıralandı
                      </span>
                    )}
                    <ModeBadge mode={response.mode} />
                  </div>
                </div>
                {response.expanded_query && (
                  <p className={styles.expanded} title="Argo/günlük dil kanonik terimlerle genişletildi">
                    <span className={styles.expandedTag}>sorgu genişletildi</span>
                    {response.expanded_query}
                  </p>
                )}
                <ResultList hits={response.results} onFeedback={handleFeedback} />
              </div>
              {response.rag_suggestion && (
                <SuggestionCard
                  suggestion={response.rag_suggestion}
                  resultCount={response.results.length}
                  ragSource={info?.rag}
                />
              )}
            </div>
          )}

          {!loading && !error && response && response.results.length === 0 && (
            <div className={styles.noHits}>
              <p>“{response.query}” için eşleşen vaka bulunamadı.</p>
              <span>Farklı belirtilerle veya daha genel ifadelerle deneyin.</span>
            </div>
          )}

          {!loading && !error && !response && <EmptyState onPick={pickExample} />}
        </div>
          </>
        )}
      </main>

      <AddFaultDrawer
        open={drawerOpen}
        categories={categories}
        onClose={() => setDrawerOpen(false)}
        onCreated={(f) => {
          setDrawerOpen(false);
          setToast({ message: `Kayıt eklendi: ${f.category}.`, kind: "success" });
          health().then(setInfo).catch(() => {});
        }}
      />

      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

/** Sağ üstteki canlı sistem durumu rozeti. */
function SystemStatus({ info }: { info: HealthResponse | null }) {
  const online = info != null;
  return (
    <div className={styles.status} data-online={online} title={online ? "Bağlı" : "Bağlantı yok"}>
      <span className={styles.statusDot} />
      {online ? (
        <span className={styles.statusText}>
          {info.fault_count} kayıt
          <span className={styles.sep}>·</span>
          {info.mode === "hybrid" ? "Hibrit arama" : "Anahtar kelime"}
        </span>
      ) : (
        <span className={styles.statusText}>Çevrimdışı</span>
      )}
    </div>
  );
}

/** Aktif kullanıcı adı + rol rozeti ve çıkış butonu. */
function UserMenu({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  if (!user) return null;
  return (
    <div className={styles.userMenu}>
      <span className={styles.userIdentity}>
        <span className={styles.userName} title={user.username}>
          {user.username}
        </span>
        <span className={styles.roleBadge} data-role={user.role}>
          {user.role}
        </span>
      </span>
      <button
        type="button"
        className={styles.logoutBtn}
        onClick={onLogout}
        title="Oturumu kapat"
      >
        Çıkış
      </button>
    </div>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  // "db" = pgvector (dense) + BM25, "hybrid" = bellek-içi dense + BM25,
  // "sparse" = yalnız BM25. İlk ikisi dense vektör kullanır.
  const dense = mode === "hybrid" || mode === "db";
  const label = mode === "db" ? "pgvector · dense + sparse" : dense ? "dense + sparse" : "sparse";
  return (
    <span className={styles.modeBadge} title={dense ? "Dense vektör + BM25" : "Yalnız BM25"}>
      {label}
    </span>
  );
}

function ResultsSkeleton() {
  return (
    <div className={styles.skeletonWrap}>
      {[0, 1, 2].map((i) => (
        <div key={i} className={styles.skeleton}>
          <div className={styles.skBar} style={{ width: "40%" }} />
          <div className={styles.skBar} style={{ width: "90%" }} />
          <div className={styles.skBlock} />
        </div>
      ))}
    </div>
  );
}
