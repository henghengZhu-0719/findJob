#!/usr/bin/env bash
# 一键启动：同步依赖 → 前端有改动就重新构建 → 启动服务（API + 页面 + 定时采集）
#
#   ./start.sh          正式模式  打开 http://127.0.0.1:8000
#   ./start.sh dev      开发模式  后端 --reload + 前端 vite 热更新，打开 http://127.0.0.1:5173
#
# 可选环境变量：HOST（默认 127.0.0.1）  PORT（默认 8000）  JOBSPIDER_CRAWL_AT（见 README 定时采集）
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-prod}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

need() { command -v "$1" >/dev/null || { echo "缺少 $1，$2" >&2; exit 1; }; }
need uv  "安装见 https://docs.astral.sh/uv/"
need npm "请先安装 Node.js"

echo "==> 同步 Python 依赖"
uv sync --quiet

# node_modules 不存在或 package*.json 比上次安装新时才装（-nt 对不存在的文件也成立）
if [ frontend/package.json -nt frontend/node_modules/.package-lock.json ] ||
   [ frontend/package-lock.json -nt frontend/node_modules/.package-lock.json ]; then
  echo "==> 安装前端依赖"
  (cd frontend && npm install)
  touch frontend/node_modules/.package-lock.json
fi

case "$MODE" in
  prod)
    if [ ! -f static/index.html ] || [ -n "$(find frontend/src frontend/index.html \
        frontend/package.json frontend/vite.config.js -newer static/index.html -print -quit)" ]; then
      echo "==> 前端有改动，重新构建"
      (cd frontend && npm run build)
    fi
    echo "==> 启动服务 http://$HOST:$PORT  （Ctrl+C 停止）"
    exec uv run python -m uvicorn main:app --host "$HOST" --port "$PORT"
    ;;
  dev)
    # 直接起 vite 而非 npm run dev，少一层进程，退出时 kill 能打到正主
    (cd frontend && API_PORT="$PORT" exec ./node_modules/.bin/vite --host "$HOST") &
    VITE_PID=$!
    trap 'kill "$VITE_PID" 2>/dev/null || true' EXIT
    trap 'exit 130' INT TERM
    echo "==> 开发模式：页面 http://$HOST:5173  接口 http://$HOST:$PORT  （Ctrl+C 停止）"
    uv run python -m uvicorn main:app --reload --host "$HOST" --port "$PORT"
    ;;
  *)
    echo "用法: ./start.sh [dev]" >&2
    exit 1
    ;;
esac
