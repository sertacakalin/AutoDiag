"""Gözlemlenebilirlik — Prometheus metrikleri + yapısal log.

/metrics ucu Prometheus formatında istek sayısı, gecikme histogramı ve iş
metriklerini (arama/teşhis sayısı, retrieval gecikmesi) sunar. Grafana ile
panolaştırılabilir (eval/grafana_dashboard.json).
"""

from __future__ import annotations

import logging
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# --- Metrikler ---
REQUESTS = Counter(
    "autodiag_requests_total", "Toplam HTTP isteği", ["method", "endpoint", "status"]
)
LATENCY = Histogram(
    "autodiag_request_seconds", "İstek gecikmesi (sn)", ["endpoint"]
)
SEARCHES = Counter("autodiag_searches_total", "Toplam arama sayısı")
DIAGNOSES = Counter("autodiag_diagnoses_total", "Toplam GraphRAG teşhis sayısı")
RETRIEVAL_LATENCY = Histogram(
    "autodiag_retrieval_seconds", "Retrieval/arama hattı gecikmesi (sn)"
)


def setup_logging(level: str = "INFO") -> None:
    """Yapısal (zaman damgalı, seviyeli) log yapılandırması."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s · %(message)s",
        datefmt="%H:%M:%S",
    )


async def metrics_middleware(request: Request, call_next):
    """Her isteğin sayısını ve gecikmesini ölç."""
    endpoint = request.url.path
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        REQUESTS.labels(request.method, endpoint, "500").inc()
        raise
    LATENCY.labels(endpoint).observe(time.perf_counter() - start)
    REQUESTS.labels(request.method, endpoint, str(status)).inc()
    return response


def metrics_endpoint() -> Response:
    """Prometheus scrape ucu."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
