// Oturum durumunu uygulama geneline taşıyan React Context.
// Jeton + kullanıcı localStorage'da kalıcıdır; açılışta getMe() ile doğrulanır.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  getMe,
  login as apiLogin,
  register as apiRegister,
  TOKEN_KEY,
  USER_KEY,
} from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  /** Açılış doğrulaması veya istek sürerken true. */
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, role?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** localStorage'dan kayıtlı kullanıcıyı güvenle okur (bozuksa null). */
function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

/** localStorage'dan kayıtlı jetonu güvenle okur. */
function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Oturum verilerini localStorage'a yazar. */
function persistSession(token: string, user: User): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* depolama kotası/erişim hatası — sessizce geç */
  }
}

/** Oturum verilerini localStorage'dan siler. */
function clearStoredSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    /* sessizce geç */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // İlk değerleri senkron olarak localStorage'dan tohumla (yanıp sönmeyi azaltır).
  const [token, setToken] = useState<string | null>(() => readStoredToken());
  const [user, setUser] = useState<User | null>(() => readStoredUser());
  // Açılışta jeton varsa doğrulanana kadar yükleniyor durumunda kal.
  const [loading, setLoading] = useState<boolean>(() => readStoredToken() != null);

  const logout = useCallback(() => {
    clearStoredSession();
    setToken(null);
    setUser(null);
  }, []);

  // Açılış: kayıtlı jeton varsa getMe() ile doğrula; geçersizse oturumu kapat.
  useEffect(() => {
    const stored = readStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        // Doğrulanan taze kullanıcıyı yeniden kalıcılaştır.
        persistSession(stored, me);
      })
      .catch(() => {
        // 401 dahil her hata: oturumu temizle (client zaten storage'ı sildi).
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    persistSession(res.access_token, res.user);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(
    async (username: string, password: string, role?: string) => {
      const res = await apiRegister(username, password, role);
      persistSession(res.access_token, res.user);
      setToken(res.access_token);
      setUser(res.user);
    },
    [],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: token != null && user != null,
      loading,
      login,
      register,
      logout,
    }),
    [user, token, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Oturum durumuna erişim. AuthProvider dışında çağrılırsa hata fırlatır. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth, <AuthProvider> içinde kullanılmalıdır.");
  }
  return ctx;
}
