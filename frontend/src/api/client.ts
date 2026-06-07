// Backend HTTP istemcisi. Tek sorumluluk: fetch çağrılarını sarmalamak,
// hataları anlamlı mesajlara çevirmek, JSON tiplemesini garanti etmek.

import type {
  AuthResponse,
  DiagnoseResponse,
  FaultCreatePayload,
  FaultRead,
  FeedbackPayload,
  HealthResponse,
  InteractiveDiagnoseResponse,
  SearchOptions,
  SearchResponse,
  User,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** localStorage anahtarları — AuthContext ile paylaşılır. */
export const TOKEN_KEY = "autodiag_token";
export const USER_KEY = "autodiag_user";

/** Backend'in döndüğü hata gövdesini okunabilir bir mesaja çevirir. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * 401 (yetkisiz) durumunda fırlatılır. Üst katman (AuthContext) bunu
 * yakalayıp oturumu sonlandırır ve kullanıcıyı giriş ekranına yönlendirir.
 */
export class UnauthorizedError extends ApiError {
  constructor(message = "Oturum süresi doldu, lütfen tekrar giriş yapın.") {
    super(message, 401);
    this.name = "UnauthorizedError";
  }
}

/** Geçerli erişim jetonunu localStorage'dan okur (yoksa null). */
function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Oturum verilerini temizler (401 veya logout). */
function clearSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    /* localStorage erişilemez — sessizce geç */
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Jeton varsa Authorization başlığını ekle; yoksa hiç ekleme.
  const token = readToken();
  const authHeader: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...authHeader,
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch {
    // Ağ seviyesinde hata: backend kapalı, CORS, DNS vb.
    throw new ApiError(
      "Sunucuya ulaşılamadı. Backend çalışıyor mu? (uvicorn app.main:app)",
      0,
    );
  }

  if (res.status === 401) {
    // Jeton geçersiz/süresi dolmuş: oturumu temizle, üst katman yönlendirsin.
    clearSession();
    const detail = await extractDetail(res);
    throw new UnauthorizedError(detail || undefined);
  }

  if (!res.ok) {
    const detail = await extractDetail(res);
    throw new ApiError(detail, res.status);
  }

  return (await res.json()) as T;
}

async function extractDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      return body.detail[0].msg as string;
    }
  } catch {
    /* gövde JSON değil — varsayılan mesaja düş */
  }
  return `İstek başarısız (HTTP ${res.status}).`;
}

/** Geçmiş vakalarda hibrit arama + (istenirse) teşhis önerisi. */
export function search(
  query: string,
  opts: SearchOptions = {},
): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({
      query,
      category: opts.category || null,
      dtc_code: opts.dtcCode || null,
      top_k: opts.topK ?? 5,
      use_rag: opts.useRag ?? true,
      rerank: opts.rerank ?? true,
      expand_query: opts.expandQuery ?? true,
    }),
  });
}

/** Yeni arıza kaydı ekler. */
export function addFault(payload: FaultCreatePayload): Promise<FaultRead> {
  return request<FaultRead>("/api/faults", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Bir sonuç için faydalı/değil geri bildirimi gönderir. */
export function sendFeedback(payload: FeedbackPayload): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/api/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Servis sağlığı: mod, kayıt sayısı, kategoriler. */
export function health(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

/** GraphRAG tek-atış yapısal teşhis (retrieval + bilgi grafiği füzyonu). */
export function diagnose(query: string, topK = 5): Promise<DiagnoseResponse> {
  return request<DiagnoseResponse>("/api/diagnose", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

// --- Kimlik doğrulama uçları ---

/** Kullanıcı adı + parola ile giriş. Başarıda jeton + kullanıcı döner. */
export function login(username: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

/** Yeni hesap oluşturur. role belirtilmezse backend varsayılanı kullanılır. */
export function register(
  username: string,
  password: string,
  role?: string,
): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(role ? { username, password, role } : { username, password }),
  });
}

/** Mevcut jetonun sahibi olan kullanıcıyı döndürür (oturum doğrulama). */
export function getMe(): Promise<User> {
  return request<User>("/api/auth/me");
}

/** Diyaloglu (aktif) teşhis — durumsuz; biriken yanıtları taşır. */
export function diagnoseInteractive(
  query: string,
  confirmed: string[],
  denied: string[],
  topK = 5,
): Promise<InteractiveDiagnoseResponse> {
  return request<InteractiveDiagnoseResponse>("/api/diagnose/interactive", {
    method: "POST",
    body: JSON.stringify({ query, confirmed, denied, top_k: topK }),
  });
}
