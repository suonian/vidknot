# VidkNot 致谢与外部项目引用

VidkNot 项目使用了以下开源项目，特此致谢。

---

## 核心引用项目

### yt-dlp

- **项目**: yt-dlp
- **作者**: yt-dlp Team
- **地址**: https://github.com/yt-dlp/yt-dlp
- **许可证**: Unlicense (Public Domain)
- **使用范围**: 视频/音频下载、多平台支持、短链接解析
- **使用方式**: 直接调用命令行工具或 Python API

### faster-whisper

- **项目**: Faster Whisper
- **作者**: SYSTRAN
- **地址**: https://github.com/SYSTRAN/faster-whisper
- **许可证**: MIT
- **使用范围**: 本地语音识别（已移除，当前使用云端）

### SiliconFlow

- **服务**: SiliconFlow
- **地址**: https://cloud.siliconflow.cn/
- **使用范围**: 云端语音识别（SenseVoice 模型）
- **许可证**: 服务商提供

### OpenAI

- **项目**: OpenAI Python Client
- **地址**: https://github.com/openai/openai-python
- **许可证**: Apache-2.0
- **使用范围**: LLM API 调用

---

## 设计参考

### 架构设计参考

本项目的架构设计参考了以下项目的设计理念：

1. **LangChain**: Agent 管道模式
   - https://github.com/langchain-ai/langchain

2. **Notion API**: 文档存储模式
   - https://developers.notion.com/

3. **Obsidian**: 本地知识库模式
   - https://obsidian.md/

---

## 特别致谢

感谢所有开源社区的贡献者，特别是：

- yt-dlp 团队维护的多平台下载器
- Faster Whisper 团队的高效语音识别
- 硅基流动团队提供的 SenseVoice 模型

---

## 许可证说明

VidkNot 项目本身采用 [MIT License](LICENSE)。

本项目使用的开源组件各有其许可证，使用时请遵守各组件的许可证要求。

主要许可证类型：

| 组件 | 许可证 |
|------|--------|
| yt-dlp | Public Domain |
| OpenAI Client | Apache-2.0 |
| FastAPI | MIT |
| PyYAML | MIT |

---

## 反馈与贡献

如果您发现任何许可证问题，请提交 Issue，我们会及时处理。
