"""AutoDiag FastAPI uygulaması.

Başlangıçta arama motorunu kurar. Demo/sunum modunda CSV'den beslenen
bellek-içi hibrit motor (`MemoryEngine`) kullanılır; Postgres+pgvector hazır
olduğunda aynı arayüzle DB motoruna geçilebilir.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import faults, feedback, search
from app.config import get_settings
from app.schemas import HealthResponse
from app.services.memory_store import MemoryEngine

# Korpus seçimi: ölçeklenmiş veri kümesi varsa onu, yoksa çekirdek seed'i kullan.
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATASET_CSV = _DATA_DIR / "faults_dataset.csv"
SEED_CSV = _DATA_DIR / "faults_seed.csv"
CORPUS_CSV = DATASET_CSV if DATASET_CSV.exists() else SEED_CSV

# Tarayıcıdan erişim için izinli kökenler (Vite dev sunucuları).
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Açılışta motoru kur, geri bildirim deposunu hazırla."""
    if CORPUS_CSV.exists():
        app.state.engine = MemoryEngine.from_csv(CORPUS_CSV)
        print(
            f"[main] {app.state.engine.count} kayıt yüklendi "
            f"({CORPUS_CSV.name}, mod: {app.state.engine.mode})."
        )
    else:
        app.state.engine = MemoryEngine([])
        print(f"[main] UYARI: korpus CSV bulunamadı: {CORPUS_CSV}")
    app.state.feedback = []
    yield
    # Kapanışta özel temizlik gerekmiyor (bellek-içi).


app = FastAPI(
    title="AutoDiag",
    description="Otomotiv arıza teşhis destek sistemi — hibrit arama + RAG öneri.",
    version="0.9.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(faults.router)
app.include_router(feedback.router)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Servis sağlığı: aktif mod, kayıt sayısı, kategoriler, RAG kaynağı."""
    from app.services.rerank import is_available

    engine: MemoryEngine = app.state.engine
    rag_source = "llm" if get_settings().LLM_API_KEY else "extractive"
    return HealthResponse(
        mode=engine.mode,
        fault_count=engine.count,
        categories=engine.categories,
        rag=rag_source,  # type: ignore[arg-type]
        rerank_available=is_available(),
    )
