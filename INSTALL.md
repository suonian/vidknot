# VidkNot 安装指南

本文档提供详细的安装步骤。

---

## 系统要求

| 要求 | 最低版本 |
|------|----------|
| Python | 3.10 |
| FFmpeg | 任意版本 |
| 磁盘空间 | 500MB+ |
| 内存 | 4GB+ |

### 支持的操作系统

- Windows 10/11 ✅
- macOS 10.15+ ✅
- Linux (Ubuntu 20.04+) ✅

---

## 安装步骤

### 1. 安装 Python

#### Windows

1. 下载 Python 3.10+: https://www.python.org/downloads/
2. 安装时勾选 **Add Python to PATH**
3. 验证安装：
   ```powershell
   python --version
   ```

#### macOS

```bash
brew install python@3.11
```

#### Linux

```bash
sudo apt update
sudo apt install python3.10 python3-pip
```

### 2. 安装 FFmpeg

#### Windows

**方法一：winget（推荐**

```powershell
winget install Gyan.FFmpeg
```

**方法二：手动安装**

1. 下载: https://ffmpeg.org/download.html
2. 解压到 `C:\ffmpeg\bin`
3. 添加到 PATH 环境变量

#### macOS

```bash
brew install ffmpeg
```

#### Linux

```bash
sudo apt install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg    # CentOS/RHEL
```

### 3. 验证 FFmpeg

```bash
ffmpeg -version
```

### 4. 安装 VidkNot

#### 稳定版

```bash
pip install vidknot
```

#### 开发版

```bash
git clone https://github.com/yourusername/vidknot.git
cd vidknot
pip install -e .
```

#### 包含飞书支持

```bash
pip install vidknot[feishu]
```

#### 完整安装

```bash
pip install vidknot[all]
```

### 5. 验证安装

```bash
python -m vidknot --version
```

---

## 配置 API Key

### 1. 获取 API Key

#### SiliconFlow（语音转录）

1. 注册: https://cloud.siliconflow.cn/
2. 控制台 → API Keys → 创建
3. 复制 Key

#### OpenAI（LLM）

1. 注册: https://platform.openai.com/
2. API Keys → 创建
3. 复制 Key

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# Windows PowerShell
notepad $env:USERPROFILE\.env

# macOS/Linux
nano ~/.env
```

内容：

```bash
SILICONFLOW_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
```

### 3. 验证配置

```bash
python -c "from vidknot import VideoKnowledgePipeline; print('OK')"
```

---

## 测试运行

```bash
# 测试下载
python -m vidknot "https://b23.tv/0G1ohFb" --destination none --no-cache
```

预期输出：
```
正在下载...
下载完成
正在转录...
转录完成
正在生成笔记...
笔记生成完成
```

---

## 常见问题

### 1. pip 找不到包

```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用国内镜像
pip install vidknot -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. FFmpeg 未找到

```powershell
# Windows 添加环境变量
$env:PATH = "$env:PATH;C:\ffmpeg\bin"
```

### 3. 权限错误

```bash
# Linux/macOS
sudo pip install vidknot
```

### 4. SSL 错误

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org vidknot
```

---

## 卸载

```bash
pip uninstall vidknot
```

---

## Docker 安装（可选）

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg

RUN pip install vidknot

WORKDIR /app
COPY . .

CMD ["vidknot", "--help"]
```

构建：

```bash
docker build -t vidknot .
docker run -v $(pwd):/app vidknot "URL"
```
