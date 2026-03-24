#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 docker，请先安装 Docker。" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "[deploy] 未找到 .env，已从 .env.example 复制；请编辑 .env 填入 LLM 等配置。"
  cp -f .env.example .env
fi

echo "[deploy] 构建并启动（Nginx 80 → app:8001）..."
if docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
else
  docker-compose up -d --build
fi

echo "[deploy] 完成。"
echo "  http://<服务器IP>/          页面与 API"
echo "  http://<服务器IP>/docs      Swagger"
echo "  查看日志: docker compose logs -f app"
echo "  查看 Nginx: docker compose logs -f nginx"
