// Backend şemalarıyla birebir eşleşen tip tanımları (app/schemas.py).

export type Confidence = "düşük" | "orta" | "yüksek";

export interface SearchHit {
  fault_id: string;
  similarity: number; // 0–1
  description: string;
  solution: string;
  category: string;
  dtc_code: string | null;
  vehicle_model: string | null;
  mileage_km: number | null;
  rerank_score?: number | null;
}

export interface RagSuggestion {
  likely_cause: string;
  recommended_steps: string[];
  confidence: Confidence;
}

export interface SearchResponse {
  results: SearchHit[];
  rag_suggestion: RagSuggestion | null;
  query: string;
  expanded_query: string | null;
  mode: string; // "hybrid" | "sparse"
  reranked: boolean;
}

export interface SearchOptions {
  category?: string | null;
  dtcCode?: string | null;
  topK?: number;
  useRag?: boolean;
  rerank?: boolean;
  expandQuery?: boolean;
}

export interface FaultCreatePayload {
  description: string;
  category: string;
  solution: string;
  dtc_code?: string | null;
  vehicle_model?: string | null;
  mileage_km?: number | null;
}

export interface FaultRead extends FaultCreatePayload {
  fault_id: string;
}

export interface FeedbackPayload {
  query_text: string;
  returned_fault_id: string;
  was_helpful: boolean;
}

export interface HealthResponse {
  status: "ok";
  mode: string;
  fault_count: number;
  categories: string[];
  rag: "llm" | "extractive";
  rerank_available?: boolean;
}
