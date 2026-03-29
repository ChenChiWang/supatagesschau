#!/bin/bash
# NAS Pipeline 更新腳本
# 用法：
#   ./update.sh              # 更新程式碼 + rebuild + 重啟排程
#   ./update.sh 2026-03-28   # 更新 + 補跑指定日期

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.nas.yml"

echo "📦 Git pull..."
docker run --rm -v "$REPO_DIR:/repo" -w /repo alpine/git pull

echo "🔨 Build pipeline image..."
docker compose -f "$COMPOSE_FILE" build pipeline

echo "🔄 重啟 scheduler（套用新 image）..."
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d scheduler

echo "✅ 更新完成"

# 如果有帶日期參數，補跑 pipeline
if [ -n "$1" ]; then
    echo "🚀 補跑 $1..."
    docker compose -f "$COMPOSE_FILE" run -e TARGET_DATE="$1" pipeline
fi
