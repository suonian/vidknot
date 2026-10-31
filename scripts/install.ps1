# ============================================================
# VidkNot 一键安装 / 验证脚本（Windows PowerShell）
# ============================================================
# 用途:
#   1. 一键安装 vidknot 包
#   2. 检查环境依赖（Python / ffmpeg），ffmpeg 缺失时自动安装
#   3. 准备 .env 模板（如不存在）
#   4. 运行 demo 模式验证安装
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#   或在仓库根目录:  .\scripts\install.ps1
#
# 高级选项:
#   $env:VERSION = "v0.6.12"                # 指定版本
#   $env:SKIP_DEMO = "1"                    # 跳过 demo 验证
#   $env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"   # 指定 pip 源
#
# 国内网络:
#   脚本会自动探测 pypi.org 连通性，不可达时自动切换清华镜像；
#   GitHub 拉取受阻时可先设置代理:
#     $env:https_proxy = "http://127.0.0.1:7890"
# ============================================================

$ErrorActionPreference = "Stop"

# ---------- 配置 ----------
$Version    = if ($env:VERSION) { $env:VERSION } else { "v0.6.12" }
$RepoUrl    = if ($env:REPO_URL) { $env:REPO_URL } else { "https://github.com/suonian/vidknot.git" }
$SkipDemo   = if ($env:SKIP_DEMO) { $env:SKIP_DEMO } else { "0" }
$PythonBin  = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

function Info($m) { Write-Host "[INFO]  $m" -ForegroundColor Blue }
function Ok($m)   { Write-Host "[OK]    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "[ERR]   $m" -ForegroundColor Red }

Write-Host "=============================================================="
Write-Host "  VidkNot $Version - 一键安装 (Windows)"
Write-Host "=============================================================="
Write-Host ""

# ---------- 0. 探测 pip 源（国内网络自动切换清华镜像）----------
$PipIndexArgs = @()
if ($env:PIP_INDEX_URL) {
    $PipIndexArgs = @("-i", $env:PIP_INDEX_URL)
    Info "使用指定 pip 源: $($env:PIP_INDEX_URL)"
} else {
    Info "探测 pypi.org 连通性..."
    $reachable = $false
    try {
        $probe = & $PythonBin -c "import socket; socket.setdefaulttimeout(4); socket.create_connection(('pypi.org', 443)).close()" 2>$null
        $reachable = ($LASTEXITCODE -eq 0)
    } catch {
        $reachable = $false
    }
    if ($reachable) {
        Info "pypi.org 可达，使用官方源"
    } else {
        $PipIndexArgs = @("-i", "https://pypi.tuna.tsinghua.edu.cn/simple")
        Warn "pypi.org 不可达，自动切换清华镜像（可用 PIP_INDEX_URL 覆盖）"
    }
}

# ---------- 1. 检查 Python ----------
Info "检查 Python..."
if (-not (Get-Command $PythonBin -ErrorAction SilentlyContinue)) {
    Err "Python 未找到: $PythonBin"
    Err "请先安装 Python 3.10+（https://www.python.org/downloads/），安装时勾选 Add Python to PATH"
    exit 1
}
$PyVersion = & $PythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$TooOld = & $PythonBin -c "import sys; print(sys.version_info < (3,10))"
if ($TooOld -eq "True") {
    Err "Python 版本过低: $PyVersion（需要 3.10+）"
    exit 1
}
Ok "Python $PyVersion"

# ---------- 2. 检查并自动安装 ffmpeg ----------
function Install-FFmpeg {
    # 优先 winget，其次 scoop / choco；都没有就用内置静态版
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Info "通过 winget 安装 FFmpeg..."
        winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements | Out-Null
        return $true
    }
    if (Get-Command scoop -ErrorAction SilentlyContinue) {
        Info "通过 scoop 安装 FFmpeg..."
        scoop install ffmpeg | Out-Null
        return $true
    }
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Info "通过 chocolatey 安装 FFmpeg..."
        choco install ffmpeg -y | Out-Null
        return $true
    }
    return $false
}

Info "检查 ffmpeg..."
$BundledFFmpeg = 0
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Ok "ffmpeg: $((& ffmpeg -version 2>&1 | Select-Object -First 1))"
} else {
    Warn "ffmpeg 未找到，尝试自动安装..."
    $installed = $false
    try { $installed = Install-FFmpeg } catch { $installed = $false }
    if ($installed -and (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Ok "ffmpeg 自动安装成功: $((& ffmpeg -version 2>&1 | Select-Object -First 1))"
    } else {
        Warn "系统级安装失败，将使用内置静态 FFmpeg（imageio-ffmpeg，无需管理员权限）"
        $BundledFFmpeg = 1
    }
}

# ---------- 3. 安装 vidknot ----------
Info "安装 vidknot@$Version..."
& $PythonBin -m pip install --upgrade pip @PipIndexArgs | Out-Null
$InstallTarget = "vidknot @ git+$RepoUrl@$Version"
if ($BundledFFmpeg -eq 1) {
    $InstallTarget = "vidknot[bundled-ffmpeg] @ git+$RepoUrl@$Version"
}
& $PythonBin -m pip install @PipIndexArgs $InstallTarget
if ($LASTEXITCODE -ne 0) {
    Err "pip 安装失败。若因 GitHub 访问受阻，可先设置代理后重试:"
    Err "  `$env:https_proxy = 'http://127.0.0.1:7890'"
    exit 1
}
Ok "vidknot@$Version 安装完成"

# ---------- 4. 准备 .env 模板 ----------
Info "准备 .env 模板..."
if (Test-Path ".env") {
    Ok ".env 已存在，跳过"
} elseif (Test-Path ".env.minimal") {
    Copy-Item ".env.minimal" ".env"
    Ok ".env 从 .env.minimal 创建（请填入 SILICONFLOW_API_KEY）"
    Warn "👉 请编辑 .env 填入你的 API key:  notepad .env"
} else {
    Warn "未找到 .env.minimal，请手动创建 .env"
}

# ---------- 5. 验证安装 ----------
Info "验证 vidknot 安装..."
& $PythonBin -c "import vidknot; print(f'  vidknot v{vidknot.__version__} OK')"
& $PythonBin -m vidknot --version

# ---------- 6. Demo 模式 ----------
if ($SkipDemo -eq "0") {
    Info "运行 demo 模式（零 API 调用）..."
    & $PythonBin -m vidknot --demo
    if ($LASTEXITCODE -ne 0) {
        Warn "demo 模式有问题，但核心包已安装"
    }
}

Write-Host ""
Write-Host "=============================================================="
Write-Host "  ✅ 安装完成！"
Write-Host "=============================================================="
Write-Host ""
Write-Host "下一步:"
Write-Host "  1. 编辑 .env 填入 SILICONFLOW_API_KEY:"
Write-Host "     notepad .env"
Write-Host ""
Write-Host "  2. 检查环境:"
Write-Host "     $PythonBin -m vidknot --check-env"
Write-Host ""
Write-Host "  3. 试用真实视频（需要 API key）:"
Write-Host "     $PythonBin -m vidknot 'https://www.bilibili.com/video/BVxxxxx'"
Write-Host ""
Write-Host "  4. 启动 MCP server（让 AI agent 调用）:"
Write-Host "     $PythonBin -m vidknot --mcp"
Write-Host ""
Write-Host "完整文档:"
Write-Host "  - SKILL.md          (Agent skill 标准格式)"
Write-Host "  - README.md         (项目说明)"
Write-Host "  - INSTALL.md        (安装与 Windows 注意事项)"
Write-Host "  - docs/CONFIG.md    (配置参考)"
Write-Host "  - .env.minimal      (最小配置)"
Write-Host ""
