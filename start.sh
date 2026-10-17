#!/usr/bin/env bash
# 一键启动：同步依赖 → 前端有改动就重新构建 → 启动服务（API + 页面 + 定时采集）
#
#   ./start.sh          正式模式  打开 http://127.0.0.1:8000
#   ./start.sh dev      开发模式  后端 --reload + 前端 vite 热更新，打开 http://127.0.0.1:5173
#
# 可选环境变量：HOST（默认 127.0.0.1，服务器对外用 0.0.0.0）  PORT（默认 8000）
#               JOBSPIDER_CRAWL_AT / JOBSPIDER_MAX_AGE_DAYS（见 README）
#
# 正式模式只有前端需要（重新）构建时才用到 Node.js：服务器上没装 Node，
# 可以在本地构建好 static/ 拷上去，脚本会直接沿用。
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-prod}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

need() { command -v "$1" >/dev/null || { echo "缺少 $1，$2" >&2; exit 1; }; }
need uv "安装见 https://docs.astral.sh/uv/"

echo "==> 同步 Python 依赖"
uv sync --quiet

# node_modules 不存在或 package*.json 比上次安装新时才装（-nt 对不存在的文件也成立）
npm_install() {
  if [ frontend/package.json -nt frontend/node_modules/.package-lock.json ] ||
     [ frontend/package-lock.json -nt frontend/node_modules/.package-lock.json ]; then
    echo "==> 安装前端依赖"
    (cd frontend && npm install)
    touch frontend/node_modules/.package-lock.json
  fi
}

frontend_stale() {
  [ ! -f static/index.html ] || [ -n "$(find frontend/src frontend/index.html \
      frontend/package.json frontend/vite.config.js -newer static/index.html -print -quit)" ]
}

case "$MODE" in
  prod)
    if frontend_stale; then
      if command -v npm >/dev/null; then
        npm_install
        echo "==> 前端有改动，重新构建"
        # 先构建到临时目录、成功再替换：vite 打包中途会清空输出目录，
        # 小内存机器上构建被 OOM 杀掉时，直接输出到 static/ 会连旧产物一起丢掉
        rm -rf static.new
        if (cd frontend && npm run build -- --outDir ../static.new); then
          rm -rf static && mv static.new static
        elif [ -f static/index.html ]; then
          rm -rf static.new
          echo "!!  前端构建失败（内存不足会显示 Killed），沿用现有 static/；可在别的机器构建后拷过来" >&2
        else
          rm -rf static.new
          echo "前端构建失败且没有现成的 static/，请在别的机器构建后把 static/ 拷到项目根目录" >&2
          exit 1
        fi
      elif [ -f static/index.html ]; then
        echo "!!  没有 npm，跳过前端构建，沿用现有 static/（前端源码若有改动不会生效）" >&2
      else
        cat >&2 <<'EOF'
缺少前端构建产物 static/，本机又没有 npm（Node.js），二选一：
  1) 安装 Node.js 18+ 后重跑 ./start.sh
  2) 在有 Node 的机器上 cd frontend && npm run build，把生成的 static/ 整个目录拷到项目根目录
EOF
        exit 1
      fi
    fi
    echo "==> 启动服务 http://$HOST:$PORT  （Ctrl+C 停止）"
    exec uv run python -m uvicorn main:app --host "$HOST" --port "$PORT"
    ;;
  dev)
    need npm "开发模式需要 Node.js 18+"
    npm_install
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
