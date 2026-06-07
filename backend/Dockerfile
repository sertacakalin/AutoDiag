# AutoDiag backend — FastAPI + sentence-transformers
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/.hf

WORKDIR /app

# Sistem bağımlılıkları (psycopg, torch için).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

# CPU-only torch — Linux imajında torch'un transitif olarak çektiği ~4GB'lık
# NVIDIA CUDA yığınını (cuda-toolkit, nvidia-cublas/cudnn/nccl, triton) engeller.
# Uygulama CPU'da inference yaptığı için CUDA gereksiz. sentence-transformers
# torch'u zaten kurulu bulur ve tekrar CUDA çekmez. İmaj ~6GB → ~1.5GB.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Veri ve (opsiyonel) modeller compose'da volume olarak bağlanır.
EXPOSE 8000

# Açılışta DB boşsa ingest et, sonra sunucuyu başlat (entrypoint script).
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
