#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  BabelDOC 离线安装程序"
echo "=========================================="
echo ""

# ── Pre-flight checks ─────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[ERROR] 未检测到 Docker，请先安装 Docker Engine >= 20.10"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "[ERROR] 未检测到 Docker Compose V2，请升级 Docker 或安装 docker-compose-plugin"
    exit 1
fi

echo "[INFO] Docker 版本: $(docker --version)"
echo "[INFO] Docker Compose 版本: $(docker compose version --short)"
echo ""

# ── Load Docker images ────────────────────────────────────────────────
echo "[STEP 1/2] 加载 Docker 镜像（含内置离线资源）..."
for img in images/*.tar.gz; do
    echo "  加载: $(basename "$img")"
    docker load < "$img"
done
echo "  离线资源已内置于后端镜像中，无需额外导入"
echo ""

# ── Start services ────────────────────────────────────────────────────
echo "[STEP 2/2] 启动服务..."
docker compose up -d
echo ""

echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "  访问地址: http://localhost"
echo ""
echo "  常用命令:"
echo "    查看状态:   docker compose ps"
echo "    查看日志:   docker compose logs -f"
echo "    停止服务:   docker compose down"
echo "    重启服务:   docker compose restart"
echo ""
