# VidkNot 依赖说明

本文档详细列出 VidkNot 项目使用的所有依赖项，包括直接依赖和间接依赖。

---

## 核心依赖

### yt-dlp

- **版本**: `>=2026.3.17`
- **用途**: 多平台视频/音频下载
- **文档**: https://github.com/yt-dlp/yt-dlp
- **许可证**: Unlicense (Public Domain)

### fastapi

- **版本**: `>=0.136.0`
- **用途**: FastAPI Web 框架
- **文档**: https://fastapi.tiangolo.com/
- **许可证**: MIT

### uvicorn

- **版本**: `>=0.27.0`
- **用途**: ASGI 服务器
- **文档**: https://www.uvicorn.org/
- **许可证**: BSD-3-Clause

### httpx

- **版本**: `>=0.27.0`
- **用途**: HTTP 客户端
- **文档**: https://www.python-httpx.org/
- **许可证**: BSD-3-Clause

### PyYAML

- **版本**: `>=6.0.1`
- **用途**: YAML 配置文件解析
- **文档**: https://pyyaml.org/
- **许可证**: MIT

### openai

- **版本**: `>=1.0.0`
- **用途**: OpenAI 兼容 API 客户端
- **文档**: https://github.com/openai/openai-python
- **许可证**: Apache-2.0

---

## 可选依赖

### feishu-docx

- **版本**: `>=0.1.0`
- **用途**: 飞书文档写入
- **安装**: `pip install vidknot[feishu]`
- **文档**: https://github.com/lxzln/feishu-docx
- **许可证**: MIT

---

## 间接依赖（自动安装）

| 包名 | 版本 | 用途 |
|------|------|------|
| pydantic | >=2.0 | 数据验证 |
| starlette | >=0.27.0 | ASGI 框架 |
| python-multipart | - | 表单解析 |
| anyio | >=3.7.0 | 异步框架 |
| sniffio | - | 异步 I/O |
| idna | >=3.0 | URL 编码 |
| certifi | - | CA 证书 |
| charset-normalizer | - | 字符编码检测 |
| urllib3 | >=1.25.0 | HTTP 库 |
| requests | >=2.31.0 | HTTP 客户端 |
| python-dotenv | - | 环境变量 |

---

## 开发依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| pytest | >=8.0.0 | 测试框架 |
| ruff | >=0.2.0 | 代码检查/格式化 |

---

## Python 版本要求

- **最低版本**: Python 3.10
- **推荐版本**: Python 3.11 或更高
- **测试版本**: 3.10, 3.11, 3.12

---

## 操作系统兼容性

| 系统 | 状态 | 说明 |
|------|------|------|
| Windows | ✅ 已测试 | 需要 FFmpeg |
| macOS | ✅ 兼容 | 需要 FFmpeg |
| Linux | ✅ 兼容 | 需要 FFmpeg |

---

## 安装方式

```bash
# 基础安装
pip install vidknot

# 包含飞书支持
pip install vidknot[feishu]

# 开发安装（包含测试工具）
pip install vidknot[dev]

# 完整安装
pip install vidknot[all]
```
