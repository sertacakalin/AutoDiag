#!/usr/bin/env bash
# AutoDiag sunum yardımcısı — çökme-korumalı başlatma, sağlık kontrolü, kurtarma.
#
# Kullanım:
#   ./scripts/demo.sh start     # sunumdan ~10 dk önce: stack'i kaldır + uyku/idle koruması
#   ./scripts/demo.sh check     # her şey ayakta mı? (1514 kayıt + db mode bekler)
#   ./scripts/demo.sh recover   # ÇÖKERSE: tek komutla geri getir (veri kalıcı, ~15 sn)
#   ./scripts/demo.sh stop       # sunum bitince: koruma kapat, stack'i durdur
#
# "start" çağrısı arka planda iki koruma başlatır:
#   1) caffeinate  → mac uyumaz/ekran kapanmaz (uyku = ağ kopması = Docker çökmesi)
#   2) keep-alive  → her 30 sn /health ping'i; Docker VM'i boşta duraklatmaz
set -euo pipefail

cd "$(dirname "$0")/.."
HEALTH="http://localhost:8000/health"
APP="http://localhost:8080"
PIDDIR="/tmp/autodiag-demo"
mkdir -p "$PIDDIR"

green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$1"; }

wait_health() {
  yellow "Sağlık bekleniyor (en fazla 90 sn)..."
  for _ in $(seq 1 45); do
    if curl -fs "$HEALTH" >/dev/null 2>&1; then
      local out; out=$(curl -fs "$HEALTH")
      local n; n=$(printf '%s' "$out" | sed -n 's/.*"fault_count":\([0-9]*\).*/\1/p')
      green "OK → $out"
      [ "${n:-0}" -ge 1500 ] && green "Kayıt sayısı sağlam ($n)." || yellow "DİKKAT: kayıt sayısı düşük ($n) — re-seed gerekebilir."
      return 0
    fi
    sleep 2
  done
  red "Sağlık alınamadı. './scripts/demo.sh recover' deneyin."
  return 1
}

start_guards() {
  # 1) Uyku engelleyici
  if [ ! -f "$PIDDIR/caffeinate.pid" ] || ! kill -0 "$(cat "$PIDDIR/caffeinate.pid" 2>/dev/null)" 2>/dev/null; then
    caffeinate -dimsu & echo $! > "$PIDDIR/caffeinate.pid"
    green "Uyku koruması açık (caffeinate, pid $(cat "$PIDDIR/caffeinate.pid"))."
  fi
  # 2) Keep-alive: Docker VM'i boşta duraklamasın
  if [ ! -f "$PIDDIR/keepalive.pid" ] || ! kill -0 "$(cat "$PIDDIR/keepalive.pid" 2>/dev/null)" 2>/dev/null; then
    ( while true; do curl -fs "$HEALTH" >/dev/null 2>&1 || true; sleep 30; done ) &
    echo $! > "$PIDDIR/keepalive.pid"
    green "Keep-alive ping açık (30 sn, pid $(cat "$PIDDIR/keepalive.pid"))."
  fi
}

stop_guards() {
  for g in caffeinate keepalive; do
    if [ -f "$PIDDIR/$g.pid" ]; then
      kill "$(cat "$PIDDIR/$g.pid")" 2>/dev/null || true
      rm -f "$PIDDIR/$g.pid"
      green "$g durduruldu."
    fi
  done
}

ensure_docker() {
  if ! docker info >/dev/null 2>&1; then
    yellow "Docker daemon kapalı — Docker Desktop başlatılıyor..."
    open -a Docker
    for _ in $(seq 1 45); do docker info >/dev/null 2>&1 && break; sleep 2; done
    docker info >/dev/null 2>&1 || { red "Docker açılmadı. Docker Desktop'ı elle başlatın."; exit 1; }
  fi
  green "Docker daemon ayakta."
}

case "${1:-}" in
  start)
    ensure_docker
    docker compose up -d
    wait_health
    start_guards
    green "Hazır. Uygulama: $APP"
    open "$APP" 2>/dev/null || true
    ;;
  check)
    ensure_docker
    docker compose ps
    wait_health
    ;;
  recover)
    red "KURTARMA modu — veri kalıcı (pgdata volume), kaybolmaz."
    ensure_docker
    docker compose up -d
    wait_health
    start_guards
    green "Geri geldi. Sunuma devam: $APP"
    ;;
  stop)
    stop_guards
    docker compose down
    green "Stack durduruldu, korumalar kapandı."
    ;;
  *)
    echo "Kullanım: $0 {start|check|recover|stop}"
    exit 1
    ;;
esac
