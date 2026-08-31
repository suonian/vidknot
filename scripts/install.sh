#!/usr/bin/env bash
# ============================================================
# VidkNot 一键安装 / 验证脚本
# ============================================================
# 用途:
#   1. 一键安装 vidknot 包
#   2. 检查环境依赖（Python / ffmpeg），ffmpeg 缺失时自动安装
#   3. 准备 .env 模板（如不存在）
#   4. 运行 demo 模式验证安装
#
# 用法:
#   curl -sSL https://raw.githubusercontent.com/suonian/vidknot/main/scripts/install.sh | bash
#   或
#   bash scripts/install.sh
#
# 高级选项:
#   VERSION=v0.6.1 bash scripts/install.sh    # 指定版本
#   SKIP_DEMO=1 bash scripts/install.sh       # 跳过 demo 验证
#   PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple  # 指定 pip 源
#
# 国内网络:
#   脚本会自动探测 pypi.org 连通性，不可达时自动切换清华镜像；
#   GitHub 拉取受阻时可先设置代理:
#     export https_proxy=http://127.0.0.1:7890
# ============================================================

set -euo pipefail

# 配置
VERSION="${VERSION:-v0.6.1}"
REPO_URL="${REPO_URL:-https://github.com/suonian/vidknot.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_DEMO="${SKIP_DEMO:-0}"

# 颜色输出
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERR]${NC}   $*"; }

echo "=============================================================="
echo "  VidkNot $VERSION — 一键安装"
echo "=============================================================="
echo

# 0. 探测 pip 源（国内网络自动切换清华镜像）
# 注意：用字符串而非数组，兼容 macOS 自带 bash 3.2（set -u 下空数组展开会报错）
PIP_INDEX_ARGS=""
if [ -n "${PIP_INDEX_URL:-}" ]; then
    PIP_INDEX_ARGS="-i $PIP_INDEX_URL"
    info "使用指定 pip 源: $PIP_INDEX_URL"
else
    info "探测 pypi.org 连通性..."
    if $PYTHON_BIN - <<'EOF' >/dev/null 2>&1
import socket
socket.setdefaulttimeout(4)
socket.create_connection(("pypi.org", 443)).close()
EOF
    then
        info "pypi.org 可达，使用官方源"
    else
        PIP_INDEX_ARGS="-i https://pypi.tuna.tsinghua.edu.cn/simple"
        warn "pypi.org 不可达，自动切换清华镜像（可用 PIP_INDEX_URL 覆盖）"
    fi
fi

# 1. 检查 Python
info "检查 Python..."
if ! command -v $PYTHON_BIN >/dev/null 2>&1; then
    err "Python 未找到: $PYTHON_BIN"
    err "请先安装 Python 3.10+"
    exit 1
fi
PY_VERSION=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$($PYTHON_BIN -c 'import sys; print(sys.version_info < (3,10))')" = "True" ]; then
    err "Python 版本过低: $PY_VERSION（需要 3.10+）"
    exit 1
fi
ok "Python $PY_VERSION"

# 2. 检查并自动安装 ffmpeg
install_ffmpeg() {
    if command -v brew >/dev/null 2>&1; then
        brew install ffmpeg && return 0
    fi
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y ffmpeg && return 0
    fi
    if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y ffmpeg && return 0
    fi
    if command -v yum >/dev/null 2>&1; then
        sudo yum install -y epel-release && sudo yum install -y ffmpeg && return 0
    fi
    if command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm ffmpeg && return 0
    fi
    return 1
}

info "检查 ffmpeg..."
if command -v ffmpeg >/dev/null 2>&1; then
    ok "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
    BUNDLED_FFMPEG=0
else
    warn "ffmpeg 未找到，尝试自动安装..."
    if install_ffmpeg && command -v ffmpeg >/dev/null 2>&1; then
        ok "ffmpeg 自动安装成功: $(ffmpeg -version 2>&1 | head -1)"
        BUNDLED_FFMPEG=0
    else
        warn "系统级安装失败，将使用内置静态 FFmpeg（imageio-ffmpeg，无需系统权限）"
        BUNDLED_FFMPEG=1
    fi
fi

# 3. 安装 vidknot
info "安装 vidknot@$VERSION..."
$PYTHON_BIN -m pip install --upgrade pip $PIP_INDEX_ARGS >/dev/null 2>&1 || true
INSTALL_TARGET="vidknot @ git+$REPO_URL@$VERSION"
if [ "$BUNDLED_FFMPEG" = "1" ]; then
    INSTALL_TARGET="vidknot[bundled-ffmpeg] @ git+$REPO_URL@$VERSION"
fi
if ! $PYTHON_BIN -m pip install $PIP_INDEX_ARGS "$INSTALL_TARGET" 2>&1 | tail -3; then
    err "pip 安装失败。若因 GitHub 访问受阻，可先设置代理后重试:"
    err "  export https_proxy=http://127.0.0.1:7890"
    exit 1
fi
ok "vidknot@$VERSION 安装完成"

# 4. 准备 .env 模板
info "准备 .env 模板..."
if [ -f ".env" ]; then
    ok ".env 已存在，跳过"
elif [ -f ".env.minimal" ]; then
    cp .env.minimal .env
    ok ".env 从 .env.minimal 创建（请填入 SILICONFLOW_API_KEY）"
    warn "👉 请编辑 .env 填入你的 API key:  vim .env"
else
    warn "未找到 .env.minimal，请手动创建 .env"
fi

# 5. 验证安装
info "验证 vidknot 安装..."
$PYTHON_BIN -c "import vidknot; print(f'  vidknot v{vidknot.__version__} OK')"
$PYTHON_BIN -m vidknot --version

# 6. Demo 模式
if [ "$SKIP_DEMO" = "0" ]; then
    info "运行 demo 模式（零 API 调用）..."
    if $PYTHON_BIN -m vidknot --demo 2>&1 | tail -5; then
        ok "demo 模式成功"
    else
        warn "demo 模式有问题，但核心包已安装"
    fi
fi

echo
echo "=============================================================="
echo "  ✅ 安装完成！"
echo "=============================================================="
echo
echo "下一步:"
echo "  1. 编辑 .env 填入 SILICONFLOW_API_KEY:"
echo "     $PYTHON_BIN -m vidknot --check-env"
echo
echo "  2. 试用真实视频（需要 API key）:"
echo "     $PYTHON_BIN -m vidknot 'https://www.bilibili.com/video/BVxxxxx'"
echo
echo "  3. 启动 MCP server（让 AI agent 调用）:"
echo "     $PYTHON_BIN -m vidknot --mcp"
echo
echo "完整文档:"
echo "  - SKILL.md          (Agent skill 标准格式)"
echo "  - README.md         (项目说明)"
echo "  - docs/CONFIG.md    (配置参考)"
echo "  - .env.minimal      (最小配置)"
echo
