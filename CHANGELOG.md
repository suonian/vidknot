# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.12] - 2026-10-31

### 消除测试用例对运行环境的依赖

v0.6.11 的 CI 在 tag 上是**红**的（Linux 3.12 为 8 failed / 507 passed，
Windows 三个 Python 版本各 9 failed / 506 passed），而本地全绿——
这是一次典型的「本机环境造成的假绿」，根因是 v0.6.11 自己引入的：

- **mmx 用例依赖「本机是否装了 mmx CLI」**。v0.6.11 新增的
  `_mmx_command()` 会先用 `shutil.which("mmx")` 定位入口，未安装时返回
  `None` 并提前给出「mmx CLI 未安装」。而 `tests/test_corrector.py` 的
  原有 mmx 用例只 mock 了 `subprocess.run`，依赖旧实现里
  `except FileNotFoundError` 的兜底路径；新实现下这些用例会直接命中
  「未安装」分支而失败。本机装有 mmx 故本地假绿，CI 未装故失败。
- **标准流用例依赖宿主进程的真实流编码**。
  `test_real_streams_are_utf8_after_call` 断言当前进程的
  `sys.stdout/sys.stdin` 编码，但 pytest 会替换这些流，且不同 runner
  的控制台代码页不同（Windows runner 为 cp1252，管道到 UTF-8 控制台
  又是另一种结果）——同样是环境相关的假测试。

### Fixed

- `tests/test_corrector.py`：`TestMmxSearch` / `TestMmxChat` 增加 autouse
  fixture 固定 `shutil.which` 的返回值，使用例结果与是否安装 mmx 无关。
- `tests/test_cross_platform.py`：标准流归一化改为在**子进程**中用
  `PYTHONIOENCODING=cp1252` 构造确定的非 UTF-8 环境，断言
  `ensure_utf8_stdio()` 调用后自报 utf-8；另补一条「真实流调用不抛异常
  且三个流均可报告」的用例。

### Tests

- 全量测试 **515 → 516 passed**；Ruff 检查通过。
- **验证矩阵**：本地模拟 CI 环境（PATH 移除 npm 目录使
  `shutil.which("mmx")` 返回 `None`，同时移除 FFmpeg 目录）
  **516 passed**；常规环境（本机装有 mmx / FFmpeg）**516 passed**。
- **CI 实测**：Linux Python 3.10 / 3.11 / 3.12 与 Windows Python
  3.10 / 3.12 / 3.13 共 6 个 job **全部通过**（含新增的 Windows 矩阵）。

### Changed

- 同步版本位点至 `v0.6.12`（`pyproject.toml` / `_version.py` / `install.sh` /
  `install.ps1` / `SECURITY.md` / issue 模板 / README 双语 / `SKILL.md` /
  `INSTALL.md` / `docs/BEST_PRACTICES.md`）。
- 本次仅修复测试与环境耦合，**运行时代码与 v0.6.11 完全一致**；
  v0.6.11 的 13 项 Windows 跨平台兼容性修复全部保留。
- 因 PyPI 不允许重复上传同一版本号，`0.6.11` 的产物无法替换，
  故以新版本号 `0.6.12` 发布携带该修复的完整一致产物。

## [0.6.11] - 2026-10-31

### 跨平台兼容性修复：Windows 全链路实测

本轮以 **Windows** 为运行平台做了一次系统性跨平台审计（项目主开发环境为
macOS），共修复 **13 项**平台差异问题。其中 1 项为 P0 级缺陷：双 ASR 校正
在 Windows 上**静默失效**——流程不报错、照常产出笔记，只是交叉校验被悄悄
跳过。全部修复均附真实复现与回归测试。

### Fixed

- 修复 **CLI 默认 `--language auto` 导致本地 faster-whisper 转写必然失败**的问题。
  faster-whisper 只接受具体语言码，`"auto"` 会抛
  `ValueError: 'auto' is not a valid language code`；自动检测需传 `None`。
  此前该异常被 CLI 捕获后回退到 SiliconFlow 单源转写，因此表现为
  **双 ASR 交叉校验永远静默失效**。现将 `auto` / 空串 / `None` 统一归一为
  `None`，显式语言码原样保留（与 `OpenAITranscribeASR` 的既有处理一致）。
- 修复 **`prefer_subtitles=False` 或 `force_audio=True` 时 YouTube 下载必然失败**的问题。
  `_download_audio_direct` 跳过了「无 Cookie + SABR-only 兼容 extractor-args」
  这一最稳的分支，直接去嗅探浏览器 Cookie；而 Chrome 正在运行时 yt-dlp
  无法复制被占用的 Cookie 库（yt-dlp issue #7271），直接抛 `DownloadError`。
  现改为复用 `_download_audio` 的回退顺序：本地 Cookie 文件 → 无 Cookie
  (SABR-only 兼容) → 浏览器 Cookie 嗅探。
- 修复 **双 ASR 校正的 prompt 在换行处被截断**、导致 LLM 只看到第一行的问题。
  Windows 的 cmd.exe 把命令行参数中的换行当作命令分隔符，`mmx text chat
  --message <多行文本>` 只有第一行能送达模型，模型因此回「请提供需要校正的原文」
  而不是执行校正，校正结果变成无意义的元回应。改为用 `--messages-file`
  传临时 JSON 文件（旧版 mmx 不支持时自动回退 `--message`），
  并在调用结束后清理临时文件。
- 修复 **Windows 上 `mmx` CLI 被误判为未安装**、导致双 ASR 校正必然失败的问题。
  npm 全局安装生成的是 `.cmd` 包装器，而 Windows 的 CreateProcess 只按 `.exe`
  解析扩展名，`subprocess.run(["mmx", ...])` 必定抛 `FileNotFoundError`，
  即使 `mmx` 已正确安装。`mmx` 是 v4/v3 校正流程的联网搜证与差异仲裁依赖，
  该问题使校正必然抛 `LLMError("mmx CLI 未安装")` 并静默降级为单源转写。
  新增 `_mmx_command()` 用 `shutil.which` 解析真实入口，`.cmd` / `.bat`
  自动经 `cmd.exe /c` 调用。
- 锁定 PyAV 上界 `av>=11,<19`，修复**本地 faster-whisper 转录完全不可用**的问题。
  PyAV 19.0.0（2026-09-29）移除了 `av.open()` 的 `metadata_errors` 参数，而
  faster-whisper <=1.2.1（当前最新版，暂无上游修复）的 `decode_audio()`
  仍在传该参数，调用时抛
  `TypeError: open() got an unexpected keyword argument 'metadata_errors'`。
  该异常被 CLI 捕获后回退到 SiliconFlow 单源转写，主流程不中断，
  因此表现为**双 ASR 交叉校验静默失效**——只影响无平台字幕、必须走本地
  ASR 的视频。已在 `pyproject.toml` / `requirements.txt` 约束版本号，
  并在 `DEPENDENCIES.md` 记录原因。
- 剥离 LLM 返回内容中内联的 `<think>...</think>` 推理块。推理模型
  （如 MiniMax-M3）默认开启 thinking，会把推理过程直接写在
  `message.content` 里而非 `reasoning_content` 字段，此前会原样落库，
  导致每篇笔记开头混入推理噪音。新增 `strip_reasoning()`，仅剥离推理块；
  对不返回推理块的模型（OpenAI / GLM 等）是无操作。
- 修复**推理块未闭合时推理内容被当成笔记落库**的问题。推理模型响应被
  `max_tokens` 截断时（实测 MiniMax-M3 单条笔记的 reasoning_tokens 约
  2000，长转录时容易撞上默认 `max_tokens: 4000` 的上限），响应末尾没有
  闭合的 `</think>`，原正则匹配不上，整段推理会被当成笔记正文。
  现在 `strip_reasoning()` 会把未闭合的 `<think>` 剥离到结尾；正文为空时
  CLI 与 Pipeline 均回退到原始转录文本（`resolve_markdown()`）。
- 修复**双 ASR 校正的子进程输出被按本地代码页解码**、导致校正静默失效的问题。
  `subprocess.run(..., text=True)` 在 Windows 上用**本地代码页**（中文为
  cp936/GBK）解码子进程 stdout，而 `mmx` 是 Node CLI、输出恒为 UTF-8。
  两档后果：字节流能按 GBK 解出来时，中文变成乱码（实测「收到」→「鏀跺埌」）；
  字节流无法按 GBK 解码时抛 `UnicodeDecodeError`，而解码发生在 `subprocess`
  的读取线程里，线程崩溃后 `CompletedProcess.stdout` 变成 `None`，
  最终以 `json.loads(None)` 这种完全误导性的 `TypeError: the JSON object
  must be str, bytes or bytearray, not NoneType` 暴露。
  由于异常被 CLI 捕获后降级为单源转写，主流程不中断，**双 ASR 交叉校验
  在 Windows 上等于从未生效**；macOS 的 locale 通常就是 UTF-8，故只在
  Windows 上显形。现所有以文本模式捕获子进程输出的调用点统一显式指定
  `encoding="utf-8"` + `errors="replace"`（`errors` 保证永不因解码失败而
  丢结果），并对 `mmx` 空输出补充可诊断的错误信息（不再暴露误导性 TypeError）。
- `NoAPIKeyError` 的默认修正建议不再固定指向 `SILICONFLOW_API_KEY`，
  改为通用文案；各抛出点（SiliconFlow ASR / OpenAI ASR / OpenAI / 智谱 /
  OpenAI-compatible / 飞书 / Notion / 语雀）改为传入与自身相关的具体提示，
  避免 LLM 缺 Key 时误导用户去配置语音转写 Key。

### Added

- **`scripts/install.ps1`**：Windows 一键安装 / 验证脚本，对应 `scripts/install.sh`。
  覆盖 pip 源探测（不可达自动切清华镜像）、Python 版本检查、FFmpeg 检查与
  自动安装（winget / scoop / chocolatey，失败则退回内置静态版）、`.env`
  模板准备、版本与 demo 验证。文件以 UTF-8 with BOM 保存，保证
  Windows PowerShell 5.1 按 UTF-8 读取（无 BOM 时会按 ANSI 解码而乱码）。
- **`src/vidknot/utils/stdio.py`**：标准流编码归一化工具（`ensure_utf8_stdio`）。
- **`src/vidknot/utils/filename.py`**：跨平台文件名安全工具（禁用字符 +
  Windows 保留设备名）。

### Compatibility

本轮以 Windows 为运行平台做了一次系统性跨平台审计（项目主开发环境为
macOS），修复下列平台差异问题。

- **MCP stdio 未固定 UTF-8**（Windows）。Windows 的标准流默认是本地代码页
  （中文为 cp936/GBK），而 MCP stdio 协议 / JSON-RPC / CI 日志都要求 UTF-8。
  自研 JSON-RPC 服务用 `print(json.dumps(..., ensure_ascii=False))` 写 stdout，
  在中文 Windows 上写出的是 GBK 字节，客户端按 UTF-8 解码会得到乱码或解析失败；
  同理客户端送来的 UTF-8 JSON 也会在 `json.loads()` 之前被 GBK 解码破坏。
  新增 `utils/stdio.py`，在 CLI 与 MCP 入口统一把 stdin / stdout / stderr
  切到 UTF-8。
- **`curl -o /dev/null`**（Windows）。`/dev/null` 是 POSIX 路径，Windows 上
  curl 会报 `client returned ERROR on write`（退出码 23）。改用
  `os.devnull`（Windows 为 `NUL`），并在 curl 失败且无状态码时返回 WARNING
  而不是「HTTP 空值」。
- **Windows 保留设备名**（Windows）。`CON` / `PRN` / `AUX` / `NUL` /
  `COM1-9` / `LPT1-9` 带任意扩展名仍然保留——写 `CON.md` 时内容会进控制台、
  文件根本不生成，删除还报拒绝访问。Obsidian 笔记文件名由视频标题生成，
  标题恰好为这些名字时会丢笔记。新增 `utils/filename.py` 统一处理，
  命中保留名时加 `_` 前缀。
- **JS 运行时探测写死 `deno.exe`**（macOS / Linux）。deno 官方安装脚本在
  Windows 产出 `deno.exe`，在 macOS / Linux 上是无扩展名的 `deno`，
  原实现导致非 Windows 平台永远找不到该路径。现同时尝试两种写法，
  并补上 `shutil.which("deno")`。
- **子进程文本输出按 locale 解码**（Windows）。详见上方 Fixed 条目：
  `text=True` 未指定 `encoding` 时使用本地代码页解码，与 Node/yt-dlp 类
  工具的 UTF-8 输出冲突。本轮一并加固了 `corrector.py`（mmx ×3）、
  `env_check.py`（yt-dlp 版本探测）、`download_manager.py`（×2）、
  `cookie_health_check.py`（curl 探针）共 7 处调用点。
- **测试与本地代码页耦合**（Windows）。`tests/` 下 28 处
  `read_text()` / `write_text()` 未显式指定编码，在非 UTF-8 locale 下会
  解码失败（`test_destination_fw.py` 读中文、`test_post_run_audit.py` 写 emoji）；
  `tests/test_env_secrets.py` 还会把读到的 `config.yaml` 写回，
  存在把用户配置写成乱码的风险。已全部显式指定 `encoding="utf-8"`。
- **两项既有用例依赖 POSIX 语义**。`test_temp_subdir.py` 用 `/etc/passwd`
  作为绝对路径样例（在 Windows 上没有盘符，不算绝对路径）；
  `test_transcriber.py` 用 `clear=True` 清空整个 `os.environ`
  （会连 `USERPROFILE` 一起清掉，Windows 上 `Path.home()` 直接抛
  `RuntimeError`）。已改为平台无关写法。
- **CI 补 Windows 矩阵**。此前 CI 只跑 `ubuntu-latest`，所有平台差异类问题
  都不会被发现。现新增 `test-windows` job（Python 3.10 / 3.12 / 3.13），
  并在 `pyproject.toml` 补上 Python 3.13 classifier。

### Tests

- 新增 `tests/test_cross_platform.py`（40 项）：Windows 保留设备名的识别与
  规避、Obsidian / 下载器文件名生成、标准流 UTF-8 归一、curl 使用
  `os.devnull`、JS 运行时在有无 `.exe` 两种形态下的探测。
- 新增 `tests/test_subprocess_encoding.py`（9 项）：AST 扫描 `src/vidknot` 全库，
  守卫「凡是文本模式捕获子进程输出的调用点必须显式 `encoding="utf-8"` +
  `errors="replace"`」，防止该类问题复发；另覆盖 mmx chat / 搜证两条链路的
  编码参数，以及 stdout 为 `None` 时抛出可诊断错误而非误导性 TypeError。
- 新增 4 个测试文件、29 项用例：
  - `tests/test_reasoning_strip.py`：推理块剥离（单块 / 多块 / 跨行 / 无推理块 /
    仅推理块）、`_call_llm` 的实际请求参数、`NoAPIKeyError` 提示的指向性；
  - `tests/test_corrector_mmx.py`：`mmx` 入口解析（`.cmd` 经 `cmd.exe /c`）、
    多行 prompt 经 `--messages-file` 完整送达、临时文件清理、
    旧版 mmx 的回退路径；
  - `tests/test_transcriber_language.py`：`auto` / 空串 / `None` 归一为
    `None`，显式语言码原样保留；
  - `tests/test_youtube_download_fallback.py`：YouTube 音频下载的回退顺序
    （无 Cookie 优先、浏览器 Cookie 兜底、本地 Cookie 文件优先）。
- 调整 `tests/test_platforms.py` 中两项既有用例
  （`test_download_force_audio_skips_subtitles`、
  `test_download_prefer_subtitles_false`）：原断言「force_audio 必须走浏览器
  Cookie 嗅探」锁定的是上述缺陷本身，改为断言「跳过字幕直接下载音频」
  并优先无 Cookie 路径；回退顺序的覆盖由新增测试文件承担。
- 全量测试 **431 → 515 passed**；Ruff 检查通过。
- 真实端到端跑通两条路径，两条路径输出均无 `<think>` 推理残留：
  - **平台字幕路径**：YouTube → 平台字幕 217 字 → MiniMax-M3 生成中文结构化笔记
  - **强制双 ASR 路径**：SABR-only 旁路下载 → SiliconFlow 189 字 +
    本地 faster-whisper 257 字 / 3 段 → 8 处差异 → LLM 校正完成（修复前
    此处报 `mmx 调用异常` 并回退单源）→ 结构化笔记
- 联网搜证（`mmx search query`）单独实测：中英文查询均返回真实结果，
  标题与摘要无乱码（修复前按 GBK 解码产生乱码）。
- MCP 在 cp936 环境变量下双向 UTF-8 往返正常，中文工具描述正确。

### Changed

- `config.yaml` 的 `providers.default_provider` 由 `openai` 改为
  `openai-compatible`。原因：`config.yaml` 中 `providers.openai.api_key`
  的占位值 `YOUR_OPENAI_KEY` 非空，导致 `LLM_API_KEY` 的写入条件
  `if not target.get("api_key")`（`utils/config_manager.py`）恒不成立，
  Key 无法注入默认 provider。改用 `openai-compatible` 后，
  `LLM_API_KEY` / `LLM_BASE_URL` / `VIDKNOT_LLM_MODEL` 三者可在 CLI 与
  Python API 两条路径下均正常生效。
- 同步版本位点至 `v0.6.11`（`pyproject.toml` / `_version.py` / `install.sh` /
  `install.ps1` / `SECURITY.md` / issue 模板 / README 双语 / `SKILL.md` /
  `INSTALL.md` / `docs/BEST_PRACTICES.md`），测试徽章由 431 更新为 515 passed，
  并同步 GitHub Release 与 SkillHub 发布信息。
- 本次修复**不改变**付费 / 会员 / DRM 内容的授权边界，也不改变
  「免费优先、第三方服务需显式启用」的策略。`docs/DOUYIN_FALLBACK.md` 与
  `docs/FAQ.md` 中关于 v0.6.10 抖音 CDN 修复的历史说明保持不变。

## [0.6.10] - 2026-09-25

### Fixed

- 抖音 Layer 3 第三方 API 返回视频直链后，下载请求补充抖音来源页
  `Referer` 与移动端浏览器 `User-Agent`，修复部分 CDN 因缺少请求头而返回
  403 的兼容性问题（PR #15）。不改变免费优先、第三方服务需显式启用的策略。
- 修正小文件清理测试的假通过：测试替身接受新增请求头，并准确断言
  `视频文件异常 (4 bytes)`，避免将参数错误误判为预期的下载失败。

### Tests

- 新增请求头回归测试，以及使用真实 httpx + MockTransport 的离线测试，
  覆盖超时重试、跨域重定向、请求头保留与不附带 Cookie/Authorization。
- 全量测试 **431 passed**；Ruff 检查通过。未调用真实付费 API 或独立复测线上 CDN。

### Changed

- 同步版本位点、安装示例、双语 README、测试徽章与 Skill 发布信息。
- 补充抖音 CDN 403 排障说明；本次修复不解决过期直链、API 凭证错误、
  付费/会员/DRM 或其他授权限制，不保证所有 403 均可恢复。

## [0.6.9] - 2026-09-17

### 安全补强：CLI 首次浏览器 Cookie 导出前用户确认

skillhub 安全审计第四项建议落地。

### Added

- **CLI 交互确认**：`_try_export_cookies()` 在从浏览器导出 Cookie 前
  检测 `sys.stdin.isatty()`——仅在交互式终端（CLI 单次运行）时提示
  `确认从浏览器读取 <平台>（域: <domain>）的 Cookie？[y/N]`；
  批处理（`--batch`）、MCP 协议（stdio 非 TTY）、管道输入自动跳过
  提示。用户拒绝（输入非 y/yes）或 EOF/中断时跳过导出
- 提示文本公开本次导出目标平台的域名，与 `COOKIE_GUIDE.md` 隐私披露节
  信息一致

### Changed

- 全量版本位点同步至 `v0.6.9`

## [0.6.8] - 2026-09-17

### 安全修复：Cookie 按域名过滤 + 临时文件加固（skillhub 安全审计）

skillhub 安全评估报告指出通用下载路径中 Cookie 处理存在三个安全隐患，
本版本逐项修复。

### Fixed

- **浏览器 Cookie 按目标平台域名过滤**：原 `_try_export_cookies()` 以
  `domain_name=None` 读取浏览器**全部站点** Cookie 并写入明文文件；
  改为按平台→域名映射表（`_COOKIE_DOMAINS`）过滤，仅导出本次下载所需
  域名的 Cookie。无映射的 unknown/generic 平台跳过浏览器导出
- **临时 Cookie 文件安全加固**：文件名从固定的 `temp_cookies.txt` 改为
  `tempfile.mkstemp` 生成的随机名（前缀 `vidknot_cookies_`），权限
  设为 `0o600`（仅当前用户可读写），yt-dlp 使用完毕后立即在
  `finally` 中删除（原有清理逻辑关联更新）
- **COOKIE_GUIDE.md 新增隐私披露节**：明确说明浏览器 Cookie 读取的域名
  范围、映射表、临时文件存放位置与生命周期，推荐优先使用手动导出的本地文件

### Changed

- `base.py`：临时文件清理判断从 `"temp_cookies" in cookie_file` 更新为
  `"vidknot_cookies_" in cookie_file`
- `tests/test_platforms.py`：修复 `test_kuaishou_temp_cookie_cleanup` 与
  `test_weibo_temp_cookie_cleanup` 中的 mock 文件名以匹配新清理前缀
- 全量版本位点同步至 `v0.6.8`

## [0.6.7] - 2026-09-17

### 冲分轮：新增最佳实践指南 + MCP 文档降密度 + 评测回落排查

skillhub 评测 0.6.6 均分 4.72（0.6.3 为 4.62），针对剩余 4.5 低分项
逐项修复（纯文档，无代码逻辑变更）。

### Added

- **`docs/BEST_PRACTICES.md`** 新增最佳实践指南：长视频分段策略（ffmpeg
  无损切片 + `--batch-dir`）、ASR 模型选型与性能权衡表、批处理并发调优
  （按链接数分段建议 + 逐条隔离契约）、网络/镜像/代理加速方案、Cookie
  管理最佳实践、排障八步自检工作流、403/付费内容场景排查、多 Agent 共享
  仓库建议。与 SKILL.md / README.md 做交叉引用

### Changed

- **SKILL.md MCP 用法章节降密度**：原 5 个工具以密集 text bullet 展开
  完整签名与返回值说明，改为表格（工具/用途/签名要点三列）+ 引用调用示例
  的方式，一眼扫完结构后再深入下方 Agent 调用示例
- **SKILL.md「边界与前提条件」节**：追加 `docs/BEST_PRACTICES.md` 交叉引用
- **SKILL.md「配置文件发现」节**：第 4 项新增「性能调优、排障流程」定位句
- **SKILL.md 文件清单**：`docs/` 行补 `BEST_PRACTICES`
- **README 双语文档表**：各插入一行 `docs/BEST_PRACTICES.md`
- **accuracy 4.8→4.6 回落排查结论**：0.6.6 代码未改动下载/错误处理路径
  （仅 __main__.py + downloader.py 加 subdir 安全校验）；评分为随机波动，
  且 FAQ 错误速查表已覆盖「会员/付费/403→能力边界，不要重试」说明
- 全量版本位点同步至 `v0.6.7`（pyproject / _version / install.sh /
  SECURITY / issue 模板 / README 双语 / SKILL.md / INSTALL.md）
- 注意：skillhub publish **必须带 `--changelog`**（0.6.6 漏填教训）

## [0.6.6] - 2026-09-17

### 修复外部智能体审计发现的三个 Bug（#8 / #9 / #10，PR #12）

由外部智能体在真实使用中定位、提交并经审查返工后合并的修复。

### Fixed

- **#8 FW 时间戳段被丢弃**：新增两个不保存语义的目的地——
  `-d fw`（输出 SiliconFlow 完整文本 + FasterWhisper 时间戳段）、
  `-d fw_file`（FW 段写到 `<输出文件>.fw.txt`，须配合 `-o`，缺失即
  `exit(2)` 而非静默丢数据）。不改变老用户 `none` 的输出格式
- **#9 双 ASR 校正失败后 FW 数据丢失**：校正失败回退单源时，直接复用
  作用域内已算出的 `fw_transcription` 保留到结果中，不再重复跑 FW
  （避免白烧 CPU），也不再丢弃已得数据
- **#10 临时目录命名不规范 / 跨平台不稳定**：临时子目录规范化为
  `<platform>-<video_id>-<YYYYMMDD-HHMMSS>-<uuid6>`；下载后按真实视频
  ID 重命名；加 uuid 后缀避免并发批处理同秒竞争；`--temp-subdir`
  自定义名做三重路径穿越防护（拒绝绝对路径 / `..` /
  `is_relative_to` 越界检查）

### Added

- **FW 补跑性能守卫**：仅在 `destination in (fw, fw_file)` 时才补跑
  faster-whisper，obsidian 等默认路径零性能回归
- **23 个回归测试** (`tests/test_destination_fw.py` 11 例 +
  `tests/test_temp_subdir.py` 12 例)：覆盖新目的地端到端、FW 段保留、
  子目录命名/并发唯一性/路径穿越拒绝；测试环境无关化（autouse fixture
  绕过 CLI 依赖检查，CI 无 f2/ffmpeg 也稳定通过）
- 测试总数 406 → **429**

### Changed

- `VideoKnowledgePipeline.SUPPORTED_DESTINATIONS` 注册 `fw` / `fw_file`
  （save() 走空分支不保存）；CLI 保存路由改为白名单判断
- 全量版本位点同步至 `v0.6.6`（pyproject / _version / install.sh /
  SECURITY / issue 模板 / README 双语 / SKILL.md 快速开始安装命令 /
  测试徽章 429）；SKILL.md 与 FAQ 目的地表补 `fw` / `fw_file` 说明

## [0.6.5] - 2026-09-01

### 多源版本审计修复：CI 恢复全绿 / LICENSE 恢复 MIT 识别 / 测试环境无关化

针对本地 / GitHub / SkillHub 三端一致性审计发现的工程问题逐项修复；
功能行为无变化（CI、测试与文档基建为主）。

### Fixed

- **CI `Lint with ruff` 失败**（main 持续红灯根因，run 33455743908）
  - `utils/__init__.py`：`__all__` 补齐 `get_ffmpeg_path` /
    `retry_with_backoff` / `get_network_config` re-export（F401×3），
    import 块排序（I001）
  - `utils/retry.py`：`typing.Callable` → `collections.abc.Callable`（UP035）
- **CI `Test with pytest` 失败**（lint 修复后暴露，此前被 fail-fast 长期掩盖）
  - `tests/test_f2_helper_cli.py`：3 个 `download_one` 测试依赖开发机
    `.venv-f2/bin/f2` 真实存在，CI 环境必然失败；新增 `fake_f2_bin`
    fixture 传入 `f2_bin` 参数，测试彻底环境无关
  - 验证方式：`F2_BIN=/nonexistent/f2 pytest -q` 模拟 CI 无 f2 环境
    → 406 passed
- **`INSTALL.md` 5 处过时版本号**：`v0.2.1` → `v0.6.4`（第 3/42/45/51/65 行，
  对应 SkillHub usability/accuracy 评估扣分点）
- **测试目录 lint 清理**：`test_douyin_api.py` / `test_processor.py` 移除
  未使用 import（F401）；`test_retry.py` 局部异常类 `Permanent` →
  `PermanentError`（N818）——`ruff check src/ scripts/ tests/` 全范围 0 errors

### Changed

- **LICENSE 纯标准化**：原双语（英文+中文翻译）+ 附加说明致 GitHub
  licensee 识别为 NOASSERTION；现只保留标准 MIT 英文文本（GitHub 已恢复
  识别 `license: MIT`），中文参考翻译移入 `README.md` License 小节折叠块
- **CI 升级 `actions/setup-python` v5 → v7**（合并 dependabot #6）
- **`.gitignore` 新增 `skills/` 与 `vibe_images/`**：SkillHub CLI 本地
  安装副本与临时附件不入库

### Added

- **审计 P0 修复脚本** (`scripts/fix_audit_p0.sh`)：幂等修复 ruff 错误与
  INSTALL.md 版本号（前置检查 + 自动验证）；配套 PR 模板
  (`scripts/pr_template_audit_fix.md`)

### Removed

- **残留分支 `codex/merge-dual-asr-correction`** 及其 worktree
  `vidknot-squash-merge`：补丁已等价合并进 main（`git cherry` 证实）

## [0.6.4] - 2026-09-01

### 文档深度优化（纯文档，无代码变更）

### Changed

- **`SKILL.md` 新增集中「应避免的用法（反模式）」章节**：原先反模式说明
  分散在正文、FAQ、PLATFORMS 三处；现集中为一张 ❌/✅ 对照表（8 条），
  覆盖不支持场景与常见错误用法，并交叉引用 `docs/FAQ.md`
- **`SKILL.md` MCP 工具文档与实现对齐**：原文档列出的
  `vidknot_extract` / `vidknot_transcribe_only` / `vidknot_status`
  并不存在；更正为实际注册的 `video_knowledge` / `video_to_notes` /
  `batch_process` / `platform_status` / `search_video`（含真实签名与
  返回格式），并扩充 Agent 端调用示例（单条 + 批量）
- **`SKILL.md` 配置章节分组重构**：按 ①必填 / ②可选存储目标 /
  ③可选高级开关 三段展示，避免环境变量一次性堆叠
- **`docs/PLATFORMS.md` 限制程度写透**：快手/微博「框架就绪」含义、
  无回归记录的明示、使用前 `yt-dlp -F` 自检命令与失败兜底路径；
  视频号补充手动导出三步流程
- **`docs/EXAMPLES.md` 补两个完整案例**：批量处理（含注释的
  `urls.txt` → 命令 → 汇总输出 → 失败逐条隔离）；超长视频
  （>1 小时）`ffmpeg` 无损分段 + `--batch-dir` 处理
- **`docs/FAQ.md` 错误速查表新增「类型」列**：区分临时故障（可重试）/
  配置错误 / 能力边界，并附类型说明
- **`README.md` / `README.en.md` 国内镜像说明增强**：清华镜像同样覆盖
  yt-dlp / faster-whisper 海外依赖；本地 ASR 模型可走
  `HF_ENDPOINT=https://hf-mirror.com`
- 全量版本位点同步至 `v0.6.4`（pyproject / _version / install.sh /
  SECURITY / issue 模板 / README 双语 / SKILL.md 快速开始安装命令）

## [0.6.3] - 2026-09-01

### 市场描述通俗化改写

### Changed

- **`SKILL.md` 头部描述通俗化**：原文偏技术（「双 ASR 交叉校验」「OpenAI 兼容
  LLM」等），普通用户看不懂；改为以「一键提取视频文案和知识笔记」开头的
  大白话表述——丢个链接进来，自动听懂内容、转成文字稿、整理出摘要与重点、
  一键存进笔记软件；保留 11+ 平台清单与触发语句（搜索/评估依赖）
- **`SKILL.md` 正文开头定位句同步通俗化**：不再以「通用视频知识提取与
  研究平台框架」开头，改为场景化描述（课程、访谈、口播、测评都能处理）
- 全量版本位点同步至 `v0.6.3`（pyproject / _version / install.sh /
  SECURITY / issue 模板 / README 双语 / SKILL.md 快速开始安装命令）

## [0.6.2] - 2026-08-31

### 市场概述页中文化

### Changed

- **`SKILL.md` 全文中文化**：市场「概述」页直接渲染 SKILL.md 正文，
  此前正文为英文导致用户看到全英文页面；现已全部译为中文
  （使用指引、边界条件、快速开始、接口形态、MCP 用法、配置、
  示例、架构图、文件清单、版本规则、许可证），
  frontmatter description 保持中文不变
- 全量版本位点同步至 `v0.6.2`（pyproject / _version / install.sh /
  SECURITY / issue 模板 / README 双语 / SKILL.md 快速开始安装命令）

## [0.6.1] - 2026-08-31

### 修复时长格式化崩溃 + 展示信息中文化

### Fixed

- **视频时长格式化崩溃** (`core/processor.py`)
  - `_build_prompt` 中 duration 为 float（yt-dlp 返回值）时，
    `f"{hours:02d}"` 抛 `ValueError`，导致 B 站等实转链路在笔记生成阶段失败
  - 修复：先 `int(duration)` 再拆分时/分/秒
- **SECURITY.md 支持版本表过时**：仍标 `v0.3.x Active`，已更新为 `v0.6.x`

### Changed

- **展示信息中文化**
  - GitHub 仓库 About 描述改为中文优先
  - `SKILL.md` frontmatter description 改为中文（市场首页展示）
  - 市场副本首屏 `README.md` 改为中文版
- 全量版本位点同步至 `v0.6.1`（含补齐 `v0.6.0` 缺失的 git tag）

### Added

- **3 个新测试** (`tests/test_processor.py`)：float/int/缺失 duration 格式化
  回归（403 → 406）

## [0.6.0] - 2026-08-31

### 评估满分优化：错误引导 / 稳定性配置 / FFmpeg 兜底 / 大文件拆分

针对 skillhub 评估报告（v0.5.0）逐项优化：错误提示可引导修正、
统一重试与超时配置、FFmpeg 免安装兜底、国内镜像安装、文档边界补齐。

### Added

- **异常 hint 体系** (`utils/exceptions.py`)
  - `VidkNotError(message, details, hint)`，类级 `default_hint` 回退
  - 19 个高频异常内置修正建议；`__str__` 追加 `| 建议: ...`（无 hint 时输出不变）
- **统一重试工具** (`utils/retry.py`)
  - `retry_with_backoff()`：指数退避 + 永久错误（401/403/404）短路，零新增依赖
  - `get_network_config()`：network 配置段安全读取
- **`network:` / `cache:` 配置段** (`config.yaml`)
  - http_timeout / download_timeout / api_timeout / max_retries / backoff_base
  - cache.max_age_days 控制结果缓存过期（`CacheManager.from_config()`）
- **内置 FFmpeg 可选依赖** — `pip install 'vidknot[bundled-ffmpeg]'`
  - imageio-ffmpeg 静态二进制，离线可用；`env_check.get_ffmpeg_path()`
    四级解析（FFMPEG_PATH → which → Windows 常见路径 → imageio-ffmpeg）
  - yt-dlp `ffmpeg_location` 与子进程调用全链路贯通
- **CLI 友好错误** — `run_cli` 顶层捕获 `VidkNotError`，
  输出「❌ 错误 / 🔍 详情 / 💡 建议」并以退出码 1 结束，不再裸 traceback
- **FAQ 错误速查表** (`docs/FAQ.md`) — 错误 → 原因 → 解决，与异常 hint 对齐
- **PLATFORMS.md 增强** — Cookie 依赖列、时长/文件大小约束、付费/DRM 判断标准
- **install.sh 重写** — FFmpeg 自动安装（brew/apt/dnf/yum/pacman）、
  pip 源自动探测（清华镜像）、bundled-ffmpeg 开关
- **新测试 62 个**（341 → 403）：retry / douyin_api / xhs_parser /
  异常 hint / ⚠️ 平台（快手/微博/B站）行为

### Changed

- **大文件拆分**（评估点名）
  - `xiaohongshu.py` 620 → 471 行：解析逻辑抽取到 `core/xhs_parser.py`
  - `douyin.py` 544 → 395 行：第三方 API 客户端抽取到 `core/douyin_api.py`
    （重试改用 `utils.retry`；类上保留薄委托，测试零破坏）
- **资源加固** — 所有下载/转码子进程补 timeout；`tempfile.mktemp` → `mkstemp`
- **`_get_js_runtime_path` 修复** — macOS/Linux 上不再调用 Windows 专属 `where`
- **文档如实修正** — 微信视频号状态由 ✅ 更正为 ⚠️ 预留（代码未实现自动下载）
- 版本号 0.5.0 → 0.6.0（`pyproject.toml` / `_version.py` / SKILL.md / 双 README /
  install.sh / SECURITY.md）

## [0.5.0] - 2026-08-26

### YouTube SABR Bypass + OpenCC 繁简转换 + 审计体系 + Cookie 健康度

合并 feature/youtube-sop-and-audit 分支（Hermes/小云实战沉淀）。

### Added

- **YouTube SABR-only 绕过** (`youtube.py`)
  - `--extractor-args "youtube:player_client=android,web"` 绕过 Chrome SABR 限制
  - 无 Cookie 也能下载 YouTube 音频（Hermes 实测 7 条全部跑通）
  - 新增 `_download_audio_no_cookie()` 和 `_download_audio_direct()`
- **OpenCC 繁简自动转换** (`transcriber.py`)
  - SiliconFlow ASR 输出繁体中文时自动转简体
  - 启发式检测 + 优雅降级（opencc 未安装时跳过）
- **Post-run Audit** (`scripts/post_run_audit.py`)
  - 双重来源机械验证：笔记内容 vs 口播稿原文
  - 检测 LLM  paraphrase/drop/invent 问题
- **Cookie 健康度 Watchdog** (`utils/cookie_health_check.py`)
  - `check_cookie_health()` + `write_health_flag()`
  - 适用：周一早上自动检测，cookie 过期时生成 flag 文件
- **Codex Sample Curator** (`scripts/codex_sample_curator.py`)
  - 六关质量检查（ffprobe duration / file size / ASR chars / 关键词 / 类型覆盖 / ASR 头部）
- **F2 Helper CLI** (`scripts/f2_helper_cli.py`)
  - f2 CLI 封装，Layer 1 备用下载
- **TikHub key 凭证扫描** (`schema.py`)
  - 新增 TIKHUB_API_KEY 模式识别，防止误提交
- **文档**: `references/2026-08-25-HERMES-EXPERIENCE-REPORT.md`
- **15 个新测试** (326 → 341)

### Changed

- `_version.py` 0.4.2 → 0.5.0
- `pyproject.toml` 0.4.2 → 0.5.0

## [0.4.2] - 2026-08-10

### TikHub Layer 3 增强（小云外围硬化 + 小 Q 核心增强）

抖音 fallback 双重增强。小云（Hermes）做了外围工具层，
小 Q 在此基础上做了核心 TikHub API 集成增强。

### Added (Hermes / 小云 feature/douyin-fallback-hardening)

- **`scripts/f2_helper_cli.py`** — f2 CLI 封装 (Layer 1 备用)
- **`src/vidknot/utils/cookie_health_check.py`** — Cookie 健康度 watchdog
  - `check_cookie_health()` + `write_health_flag()`
  - 适用：周一早上自动检测，cookie 过期时生成 flag 文件
- **`scripts/codex_sample_curator.py`** — Codex 六关检查工具
  - ffprobe duration / file size / 转录字符 / 关键词匹配 / 类型覆盖 / ASR 头部
- **`src/vidknot/core/source/schema.py`** — TikHub key 模式识别
- **文献**: `docs/DOUYIN_FALLBACK.md`、`docs/PLATFORMS.md`、`docs/EXPERIENCES.md`
- **23 个新测试** (294 → 326)

### Added (小 Q — TikHub Layer 3 核心增强)

- **`_call_third_party_api`** — 新增 **exponential backoff retry**
  - max_retries=2，指数退避（1s / 2s / 4s）
  - 区分临时错误（429 限流 / 5xx 过载 / 网络超时 → 重试）
  - 区分永久错误（401 鉴权过期 / 403 无权限 / 404 不存在 → 跳过）
- **`_download_with_retry`** — 新建 CDN 直链下载重试
  - max_retries=2（1s / 2s 退避）
  - TikHub / apibyte 返回的视频直链可能来自 CDN 缓存，偶尔瞬断
- **`_parse_api_response`** — 独立的 response path 解析
  - 不再 hard-fail（DownloadError），改为 warn + return None
  - 让主循环继续到下一个 API

### Changed

- 旧 `_call_third_party_api` 方法已删除（无 retry / 无错误分类）
- `_version.py` 0.4.1 → 0.4.2
- `pyproject.toml` 0.4.1 → 0.4.2

### Verified

- 326 tests pass（294 core + 23 Hermes + 9 local fix）
- ruff lint 0 errors
- Zero regression on v0.4.1 全部功能

## [0.4.1] - 2026-08-10

## [Unreleased]

### Added

- **`scripts/codex_sample_curator.py`** — six-gate quality check
  distilled from Codex's three-round feedback (2026-08-10):
  - Gate 1: ffprobe duration ≥ 180 s
  - Gate 2: file size ≥ 1 MB
  - Gate 3: ASR transcript ≥ 1500 chars
  - Gate 4: filename-derived keywords match transcript head/tail (≥ 50%)
  - Gate 5: type coverage awareness (tool test / project retrospective /
    opinion / OPC super-individual)
  - Gate 6: transcript head rejection for known failure patterns
    (single-character spam, "音响设备故障", etc.)
- **`scripts/post_run_audit.py`** — post-run dual-source audit
  (Hermes iron rule 135 enforcement, 2026-08-25):
  - Fetches every docx in a Feishu folder, verifies each "原文"
    / "核心观点" / "原声金句" code-block line appears verbatim in
    the local `fw_corrected.txt` or `sf_corrected.txt`
  - Reports coverage + true_miss with section context
  - Returns exit code 0 iff all docs ≥ 99.0 % coverage with zero
    true_miss (CI-friendly)
  - Reference: Hermes iron rule 113 "笔记内容 = 口播稿原文" + 老大拷问
    "是否确定过笔记内容和口播稿内容一致"
- **`tests/test_post_run_audit.py`** — covers normalization, time-stamp
  stripping, OK / MISMATCH reporting, fw+sf 双源 boundary.

### Changed

- **YouTube platform** — Level 3 (audio download) now uses a 3-tier
  fallback (Hermes实战 2026-08-25, Lin Lili @linliliya 7 videos):
  1. local Cookie file (cookies/youtube.txt)
  2. **`--extractor-args "youtube:player_client=android,web"`** SABR-only
     bypass (no Cookie required, default for yt-dlp 2026+)
  3. Browser Cookie sniff (legacy fallback)
  - Hermes noted: "vt-dlp 2026+ 默认 SABR-only 拒签 web client, 必须
    指定 player_client=android,web 才能在无 Cookie 环境下下载"
- **SiliconFlowASR** — automatic Traditional Chinese → Simplified
  Chinese conversion (OpenCC `t2s`) when the transcript looks
  Traditional:
  - Heuristic: count of Traditional feature characters (經/學/聲/變/對/...)
    > 2× Simplified counterparts
  - Uses `opencc-python-reimplemented` if installed; gracefully skips
    conversion otherwise
  - Hermes noted: "Lin Lili @linliliya 全部 7 条视频都是繁体源, SF 输出
    也含繁体, 不转 LLM 提取会混入繁体"

### Documentation

- `references/2026-08-25-HERMES-EXPERIENCE-REPORT.md` — Hermes heavy-user
  perspective: 实战优势 + 上游改进建议清单
  (companion to this commit)

## [0.4.1] - 2026-08-10

### Standard Agent Skill Compliance

本次为 patch 版本（minor bump），专门为达到**标准 Agent Skill 格式**：
vidknot 现在可被 Claude / Qoder / Cursor / Cline 等 AI agent 一键识别为 skill。

### Added

- **SKILL.md**（根目录）— Agent skill 标准格式入口
  - YAML frontmatter: name / version / description / when-to-use
  - Quick start (1 minute)、4 种接口说明、配置指南、架构图
- **`--demo` 模式** — 零配置烟雾测试
  - `python -m vidknot --demo` 不需要任何 API key
  - 输出 mock 笔记展示完整 pipeline（6 步 + 模拟 Markdown）
  - 适合：agent 首次接触 / README 演示 / 教学场景
- **`.env.minimal`** — 单 API key 最小配置模板
  - 只需 `SILICONFLOW_API_KEY` 即可跑（其他 LLM/存储可选）
- **`scripts/install.sh`** — 一键安装 / 验证脚本
  - 检查 Python / ffmpeg / 安装 / .env 准备 / demo 验证
  - 可通过 `curl ... | bash` 远程运行
  - 支持 `VERSION=` `SKIP_DEMO=` `REPO_URL=` 自定义
- **MCP 工具说明** — 三个工具接口文档
  - `vidknot_extract` / `vidknot_transcribe_only` / `vidknot_status`
- **重点强调 11+ 自媒体平台**（输入源）
  - 不再以"笔记平台"为重点
  - 在所有 manifest（pyproject/README/__init__/__main__）明确"自媒 体平台 vs 笔记平台"分层

### Changed

- 项目定位重写：视频转笔记工具 → 通用研究平台框架，**重点是 11+ 自媒体平台**
- 文档交叉验证（5 个 manifest 文件 + GitHub repo description 全部一致）
- ruff lint 自动修复 4 个 errors（UP015 / W292 / 格式）

### Verified

- 294 tests pass（v0.4.0 全部保留）
- ruff lint 0 errors
- `--demo` 模式零配置可用
- `bash scripts/install.sh` 一键安装验证
- 现有核心模块零改动

### Install

```bash
# 一键安装（验证 demo）
bash scripts/install.sh

# 或手动
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.4.1"
vidknot --demo
```

## [0.4.0] - 2026-08-10

## [0.4.0] - 2026-08-10

### Platform Evolution: 视频转笔记工具 → 通用研究平台框架

本次为大版本（major bump）：vidknot 从"视频转笔记工具"升级为"通用研究平台框架"。
**完全向后兼容** —— 现有 CLI / FastAPI / MCP / Python API、11 个平台插件、ASR + 校正流水线零改动。
v0.3.4 已发布的所有功能在新版本中完全保留。

### Added (Hermes / 小云 feature/general-platform-framework)

#### 核心框架模块
- **core/backend/** — 可插拔存储抽象层
  - `NotePayload` / `StorageResult` / `BackendError` 数据类
  - `BackendStorage` 协议 + `BackendRegistry` 注册表
  - `SqliteBackend` 内置实现（路径由 `VIDKNOT_SQLITE_PATH` env 控制）
  - `build_default_registry()` 工厂函数
- **core/source/** — 订阅源 schema + 凭证注入保护
  - `SourceConfig` / `SourceKind` / `SourcesFile` 数据类
  - `load_sources_file(path)` 解析 YAML / JSON
  - **凭证拒绝机制**：加载时主动拒绝 8 类危险模式（`sessionid=` / `ttwid=` / `odin_ttid=` / `fpk1=` / `fpk2=` / `web_session=` / `AI_PASS=` / `Bearer ` / `sk-` / `SK-`）
- **core/batch/** — 批处理 driver
  - `BatchSummary` / `collect_urls()` / `run_batch()`
- **core/monitor/** — 通用周期调度器
  - `MonitorTask` (base) / `TaskRegistry` / `MonitorScheduler` / `ScheduledRun`
  - async `run_once()` 和 `run_forever(max_ticks=...)` 带上限防止泄漏
  - 错误 per-task 捕获不抛出

#### 文档
- `docs/PRIVACY.md` — 隐私声明（仓库零用户数据 / 零嵌入凭证）
- `docs/BACKENDS.md` — 后端配置（含飞书机器人接法）
- `docs/CONFIG.md` — 全部环境变量参考
- `docs/EXAMPLES.md` — 自定义 backend / task / batch / source 配方
- `examples/sources.yaml.example` — 空模板（零真实账号）

#### Tests
- `tests/test_backend.py` — 9 个测试
- `tests/test_source.py` — 20 个测试（含凭证拒绝反例）
- `tests/test_batch.py` — 8 个测试
- `tests/test_monitor.py` — 10 个测试
- **新增 47 个测试**（247 → 294）

#### Dev Dependencies
- 加 `pytest-asyncio>=0.21`（core/monitor 异步测试需要）

### Privacy & Safety

- 仓库**无 cookies / tokens / API keys**
- 仓库**无账号列表 / 频道列表 / KOL 标识**
- 仓库**无私有文件夹 / 文档 / 聊天 ID**
- `load_sources_file` 主动拒绝凭证模式注入
- 所有示例使用占位 URL

### Verified

- 294 tests pass
- ruff lint 0 errors
- 现有核心模块（platforms / transcriber / processor / downloader / cookie_provider）零改动
- v0.3.4 已发布功能完全保留

## [0.3.4] - 2026-08-10

## [0.3.4] - 2026-08-10

### Changed

- **抖音 Layer 0 (f2 XBogus) 默认改为 disabled**。Hermes agent (上海服务器) 2026-08 实测 f2 0.0.1.7 签名算法已被抖音更新，签名后 API 返回空 body。仍可通过 `enable_f2: true` 手动开启，但默认走 Layer 1+2 路径。文件: `src/vidknot/core/platforms/douyin.py:71`

### Added

- **本地 mp4/mkv/mov 视频自动转码为 mp3** (`process_local_video`)。Hermes agent 实战发现：SiliconFlow 不接受 mp4，错误信息误导为"SSL 握手失败"实际是格式不支持。`__main__.py:328-340` 检测视频格式后调 ffmpeg 抽音频，再传给 SiliconFlow。文件: `src/vidknot/__main__.py`

### Verified

- 247 个单元测试全部通过
- 与 Hermes agent 通过飞书 DM 协作完成（Qoder agent 代号"小 Q"）

## [0.3.3] - 2026-08-10

### Added

- **小红书视频笔记直链下载** (`xiaohongshu.py`)：从 `__INITIAL_STATE__.note.video.media.stream.h264[0].masterUrl` 拿无水印视频直链，多清晰度候选（HD/SD/原链）自动尝试；下载后调用 `dl._extract_audio` 抽音频用于转写。
- **笔记类型探测** (`XiaoHongShuPlatform._probe_note_type`)：从 HTML 提取 `video.media.stream` 字段判断笔记是视频还是图片，避免 yt-dlp 对小红书不可靠的 fallback。
- **平衡括号 JSON 提取器** (`_extract_balanced_json`)：处理 `__INITIAL_STATE__` 多行 JSON 截断问题，修复之前正则非贪婪导致的解析失败。
- **抖音 Layer 0: f2 X-Bogus 集成** (`scripts/f2_helper.py`)：调用 f2 库的 `XBogusManager.str_2_endpoint` 自动签名 POST_DETAIL URL，通过 `.venv-f2` 隔离依赖（结构就绪；f2 0.0.1.7 签名算法已被抖音更新，运行时仍回退 Layer 1）。
- **抖音 Cookie 支持** (`douyin_parser.parse(cookie_str=...)`)：Layer 1 自动从 `cookie_provider` 获取 Cookie 并注入请求头。
- **`COOKIE_GUIDE.md` 能力地图章节**：记录各平台可用性、抖音四层 Fallback 状态、行业级未解难题（如 X-Bogus 纯开源签名）。

### Changed

- TikHub 端点从 `api.tikhub.io`（国际）切换到 `api.tikhub.dev`（大陆直连，无需代理）。
- 小红书 `_extract_from_state` 返回签名扩展为 `(title, image_urls, video_url)`，同时支持图片和视频直链提取。
- 小红书主下载流程重构：`probe → video/image → yt-dlp → XHS-Downloader` 三层回退；探测失败（短链被风控跳首页）时自动让 video 路径接管，避免走错分支。

### Fixed

- 小红书 `_extract_note_id` 正则不支持 `xhslink.cn` 短链 → 修复。
- 小红书 `_download_images` 未保留 `xsec_token`（短链 302 后 404）→ 修复。
- 小红书 httpx.Client 未传入 Cookie → 修复。
- 小红书图片 CDN 正则未覆盖 `sns-webpic-qc.xhscdn.com` → 修复。

### Verified

- 端到端测试：一条小红书视频笔记（4:54 时长 / 7.6 MB）跑完整 pipeline：下载视频 → 抽音频 → SiliconFlow + FasterWhisper 双 ASR 转录 → 双 ASR diff → LLM 校正 → 生成结构化 Markdown 笔记，全部成功。
- 242 个单元测试全部通过。

## [0.3.2] - 2026-08-06

### Added

- **`.env` file support**: `ConfigManager` now loads `dotenv_values` from local
  `.env` files, and `python -m vidknot` calls `load_dotenv` at entry for
  consistent env views across all consumers.
- **`VIDKNOT_ENV_FILE`**: comma-separated shared credential file paths for
  multi-agent hosts (e.g. `~/.hermes/.env`). Generic `OPENAI_*` / `ZHIPUAI_MODEL`
  keys in shared files are stripped to prevent key leakage from host agents.
- **`openai-compatible` provider**: new provider block for generic OpenAI-compatible
  LLM endpoints (MiniMax, DeepSeek, etc.), configurable via `LLM_API_KEY`,
  `LLM_BASE_URL`, and `VIDKNOT_LLM_MODEL`.
- **`LLM_API_KEY` dual mapping**: applies to both `openai` and `openai-compatible`
  providers for backward compatibility.

### Changed

- `OpenAITranscribeASR._get_client()` no longer falls back to `os.getenv("OPENAI_API_KEY")`;
  key resolution is centralized in `ConfigManager._apply_env_overrides()`.
- `yt-dlp` bumped to `>=2026.07`.

### Fixed

- PyPI trove classifier `Natural Language :: Chinese (Simplified)` (was invalid
  `Chinese`, causing all release workflows to fail since v0.2.0).

## [0.3.1] - 2026-08-06

### Added

- CLI `--version` flag.
- `pipeline.run()` now includes `result["structured"]` (with `segments`) in
  structured format mode, so direct pipeline consumers get the same structured
  JSON as the CLI path.

## [0.3.0] - 2026-08-05

### Added

- **Platform plugin architecture**: new `vidknot.core.platforms` package with
  `BasePlatform` / `YtDlpPlatform` abstract classes and a `PlatformRegistry`
  (register/detect/list). Adding a platform now requires only one file + registration.
- **12 registered platforms**: YouTube, Douyin, Bilibili, XiaoHongShu, TikTok,
  Twitter/X, Instagram, Kuaishou, Weibo, Vimeo, WeChat Channels (reserved), and a
  generic yt-dlp fallback.
- **YouTube subtitle-first strategy**: youtube-transcript-api → yt-dlp subtitle
  extraction → audio download + ASR fallback, preserving timestamped segments.
- **Bilibili CC subtitle-first** with fallback to audio + ASR.
- **Douyin**: three-tier fallback migrated into the plugin (parser → browser cookie
  yt-dlp → optional third-party API, incl. self-hosted Evil0ctal via `api_base_url`).
- **XiaoHongShu**: image notes kept, video path added, optional XHS-Downloader fallback.
- **TikTok**: cobalt API integration with yt-dlp fallback.
- **Transcription layer**: new `SubtitleExtractor` (.srt/.vtt parsing) and
  `OpenAITranscribeASR` (Whisper API); `get_transcriber()` supports `openai_whisper`.
- **Structured JSON output**: `result["structured"]` with `segments`, `topics`,
  `entities`, `key_points`, `summary_one_line`, `tags`, and `correction_confidence`
  via `ContentProcessor.extract_structured()`.
- **Batch processing**: `pipeline.run_batch()` (ThreadPoolExecutor, default 3 workers)
  and CLI flags `--batch urls.txt`, `--batch-dir ./videos/`, `--max-workers`.
- **MCP multi-tool server**: `video_to_notes`, `batch_process`, `platform_status`,
  `search_video` (reserved) for both the FastMCP path and the fallback stdio server.
- **Agent bridge**: `get_all_tools_metadata()` and tool-name routing in
  `execute_tool(arguments, tool=...)`.
- **New config block** `platforms`: per-platform subtitle/cookie options plus
  `transcription.strategy` (subtitle_first/siliconflow_only/faster_whisper_only/dual_asr)
  and `transcription.fallback_provider`.
- **New dependency**: `youtube-transcript-api>=0.6.0`.
- **93 new unit tests** (226 total passing) covering platforms, batch processing,
  structured JSON, and MCP/agent tooling.

### Changed

- `VideoDownloader._download_sync()` delegates to `PlatformRegistry.detect(url)`;
  `downloader.py` reduced from ~774 to ~350 lines by moving platform logic into plugins.
- `process_video()` and `pipeline.run()` apply the subtitle-first strategy and skip ASR
  when a platform provides official subtitles.
- `agent_bridge.execute_tool()` calls the pipeline synchronously (fixes incorrect
  `asyncio.run()` usage on sync methods).

## [0.2.1] - 2026-07-30

### Changed

- Cleaned README, installation, API, dependency, and Cookie documentation.
- Updated public installation instructions to use the current GitHub release.
- Raised the optional `feishu-docx` lower bound to `>=0.2.7`.
- Synchronized `.env.example` with documented environment variables.

## [0.2.0] - 2026-07-30

### Added

- **Dual-ASR Cross-Validation Correction Pipeline**: Run two independent ASR systems
  (SiliconFlow SenseVoice + local faster-whisper) and use mmx search + LLM to
  detect and correct transcription errors.
- **New CLI flags**:
  - `--correct` / `--no-correct`: enable or disable dual-ASR correction
  - `--correction-version {v3,v4}`: choose correction strategy (v4 conservative, v3 aggressive)
- **New config block** `faster_whisper`: configure local ASR model/device/compute
- **New config keys** under `settings`: `enable_correction`, `correction_version`
- **New exception** `CorrectionError` in `vidknot.utils.exceptions`
- **New module** `vidknot.core.corrector`: `DualASRCorrector` class and
  `run_correction_pipeline()` factory function
- **New class** `vidknot.core.transcriber.FasterWhisperASR`: local CPU ASR with
  timestamped output (used as the cross-validation source)
- **Comprehensive unit tests**: 133 passing tests covering transcriber, corrector,
  pipeline, and adapters (up from 47)
- **`.gitignore`**: excludes `.vidknot_cache/`, `cookies/`, `.vidknot_tmp*.md`

### Changed

- `vidknot.__main__.process_video` now runs dual-ASR correction by default
  (controlled by `settings.enable_correction`)
- README, INSTALL, DEPENDENCIES, CREDITS docs updated to reflect dual-ASR pipeline

### Notes

- The dual-ASR pipeline falls back to SiliconFlow-only when the local ASR or
  mmx is unavailable; the rest of the flow keeps running.

## [0.1.0] - 2026-04-28

### Added

- **Video Download**: Support for multiple platforms (YouTube, Bilibili, Douyin, etc.) via yt-dlp
- **Cloud Transcription**: SiliconFlow SenseVoice API for fast and accurate speech-to-text
- **LLM Note Generation**: AI-powered structured note generation from video content
- **Multi-Platform Storage**:
  - Feishu (飞书) document integration
  - Yuque (语雀) integration
  - Notion integration
  - Obsidian local vault support
- **Multiple Run Modes**:
  - CLI mode (`python -m vidknot <url>`)
  - MCP mode for AI agent integration
  - FastAPI server mode
- **Cache System**: Intelligent caching to avoid redundant processing
- **Cookie Management**: Support for authenticated video downloads

### Features

- Synchronous processing pipeline for simplicity and reliability
- Environment-based configuration via `.env` files
- Comprehensive error handling and logging
- Cross-platform support (Windows, macOS, Linux)

### Documentation

- README.md - Project overview and quick start
- INSTALL.md - Detailed installation guide
- API_GUIDE.md - API documentation
- COOKIE_GUIDE.md - Browser cookie extraction guide
- DEPENDENCIES.md - Dependency management
- CREDITS.md - Third-party acknowledgments
- DISCLAIMER.md - Legal disclaimer

## [0.0.1] - 2026-04-01

### Added

- Initial project setup
- Basic video download functionality
- Proof of concept for video-to-notes pipeline
