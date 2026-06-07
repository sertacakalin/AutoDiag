// Kimlik doğrulama ekranı: giriş / kayıt sekmeleri, doğrulama, hata + yükleme.
// Oturum açık değilken App tarafından gösterilir.

import { useId, useState } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import styles from "./LoginScreen.module.css";

type Tab = "login" | "register";

const MIN_PASSWORD = 6;

export function LoginScreen() {
  const { login, register } = useAuth();

  const [tab, setTab] = useState<Tab>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Erişilebilirlik için kararlı id'ler (label/aria bağlantıları).
  const userId = useId();
  const passId = useId();
  const errId = useId();

  const trimmedUser = username.trim();
  // Kayıtta parola en az MIN_PASSWORD karakter olmalı.
  const passwordTooShort = tab === "register" && password.length > 0 && password.length < MIN_PASSWORD;
  const canSubmit =
    trimmedUser.length >= 3 &&
    password.length >= (tab === "register" ? MIN_PASSWORD : 1) &&
    !submitting;

  function switchTab(next: Tab) {
    if (next === tab) return;
    setTab(next);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setError(null);
    try {
      if (tab === "login") {
        await login(trimmedUser, password);
      } else {
        await register(trimmedUser, password);
      }
      // Başarı: AuthContext state'i günceller, App otomatik olarak uygulamaya geçer.
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const isLogin = tab === "login";

  return (
    <div className={styles.screen}>
      <main className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.logo} aria-hidden>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
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

        <p className={styles.intro}>
          Saha teşhis konsoluna erişmek için oturum açın. Hesabınız yoksa yeni
          bir kayıt oluşturabilirsiniz.
        </p>

        <div className={styles.tabs} role="tablist" aria-label="Kimlik doğrulama">
          <button
            type="button"
            role="tab"
            aria-selected={isLogin}
            className={styles.tab}
            data-active={isLogin}
            onClick={() => switchTab("login")}
          >
            Giriş Yap
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={!isLogin}
            className={styles.tab}
            data-active={!isLogin}
            onClick={() => switchTab("register")}
          >
            Kayıt Ol
          </button>
        </div>

        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label htmlFor={userId} className={styles.label}>
              Kullanıcı adı
            </label>
            <input
              id={userId}
              className={styles.input}
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="orn. teknisyen01"
              disabled={submitting}
              minLength={3}
              required
              autoFocus
              spellCheck={false}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor={passId} className={styles.label}>
              Parola
            </label>
            <input
              id={passId}
              className={styles.input}
              type="password"
              autoComplete={isLogin ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={submitting}
              minLength={isLogin ? undefined : MIN_PASSWORD}
              aria-describedby={passwordTooShort ? `${passId}-hint` : undefined}
              required
            />
            {!isLogin && (
              <span
                id={`${passId}-hint`}
                className={styles.hint}
                style={passwordTooShort ? { color: "var(--danger)" } : undefined}
              >
                En az {MIN_PASSWORD} karakter olmalı.
              </span>
            )}
          </div>

          {error && (
            <div id={errId} className={styles.error} role="alert">
              {error}
            </div>
          )}

          <button type="submit" className={styles.submit} disabled={!canSubmit}>
            {submitting
              ? isLogin
                ? "Giriş yapılıyor…"
                : "Hesap oluşturuluyor…"
              : isLogin
                ? "Giriş Yap"
                : "Kayıt Ol"}
          </button>
        </form>

        <p className={styles.footnote}>
          {isLogin ? "Hesabınız yok mu?" : "Zaten hesabınız var mı?"}{" "}
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              switchTab(isLogin ? "register" : "login");
            }}
          >
            {isLogin ? "Kayıt olun" : "Giriş yapın"}
          </a>
        </p>
      </main>
    </div>
  );
}
