"""
VidkNot 视频知识管道

统一处理管道：接收 URL → 返回笔记内容 → 根据配置路由到目的地
"""

from typing import Any

from ..adapters.feishu_writer import FeishuWriter
from ..adapters.notion_writer import NotionWriter
from ..adapters.obsidian_writer import ObsidianWriter
from ..adapters.yuque_writer import YuqueWriter
from ..core.downloader import VideoDownloader
from ..core.processor import ContentProcessor
from ..core.transcriber import SiliconFlowASR
from ..utils.cache_manager import CacheManager
from ..utils.exceptions import NoAPIKeyError, StorageError
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 目的地 -> 写入器的中文标签（用于错误提示）
_DESTINATION_LABELS = {
    "feishu": "飞书",
    "yuque": "语雀",
    "notion": "Notion",
    "obsidian": "Obsidian",
}

# config.yaml 里常见的占位符标记 —— 这些值不是真实凭证，必须忽略
_PLACEHOLDER_MARKERS = ("YOUR_", "CHANGE_ME", "REPLACE_ME", "请填写", "你的")


def _is_placeholder(value: Any) -> bool:
    """判断配置值是否为占位符（``YOUR_XXX`` 之类）而非真实凭证。"""
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    upper = text.upper()
    return any(marker.upper() in upper for marker in _PLACEHOLDER_MARKERS)


def _as_bool(value: Any) -> bool:
    """把配置值转成 bool（兼容 YAML 布尔与环境变量字符串）。"""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


class VideoKnowledgePipeline:
    """
    视频知识处理管道

    接收视频 URL，执行完整的处理流程：
    1. 下载音频
    2. 云端 ASR 转录（SiliconFlow SenseVoice）
    3. LLM 生成笔记
    4. 路由到目的地（飞书/语雀/Notion/Obsidian）
    """

    SUPPORTED_DESTINATIONS = [
        "feishu", "yuque", "notion", "obsidian", "both",
        # 输出增强选项（仅控制输出形式，不涉及保存语义）
        "none",        # 不保存,默认输出 SF 完整文本(原行为)
        "fw",          # 不保存,输出 SF 完整 + FW 时间戳段(issue #8 修复)
        "fw_file",     # 不保存,把 FW 段写到 *.fw.txt 文件(issue #8)
    ]

    def __init__(
        self,
        destination: str = "obsidian",
        format: str = "structured",
        language: str = "auto",
        feishu_config: dict | None = None,
        obsidian_config: dict | None = None,
        yuque_config: dict | None = None,
        notion_config: dict | None = None,
        use_cache: bool = True,
    ):
        """
        初始化管道

        Args:
            destination: 保存目的地 (feishu/yuque/notion/obsidian/both/none)
            format: 输出格式 (structured/raw)
            language: 视频语言
            feishu_config: 飞书配置
            obsidian_config: Obsidian 配置
            yuque_config: 语雀配置
            notion_config: Notion 配置
            use_cache: 是否使用缓存
        """
        if destination not in self.SUPPORTED_DESTINATIONS:
            raise ValueError(f"不支持的目的地: {destination}，支持: {self.SUPPORTED_DESTINATIONS}")

        self.destination = destination
        self.format = format
        self.language = language
        self.use_cache = use_cache

        self.downloader = VideoDownloader()
        self.transcriber = SiliconFlowASR()
        self.processor = ContentProcessor()
        self.cache = CacheManager.from_config() if use_cache else None

        self._feishu = None
        self._obsidian = None
        self._yuque = None
        self._notion = None
        self._feishu_config = feishu_config
        self._obsidian_config = obsidian_config
        self._yuque_config = yuque_config
        self._notion_config = notion_config

        if feishu_config:
            self._feishu = FeishuWriter(**feishu_config)
        if obsidian_config:
            self._obsidian = ObsidianWriter(**obsidian_config)
        # Notion / 语雀的写入器在缺凭证时构造即抛 NoAPIKeyError，
        # 因此不预热，改为保存时惰性构造（错误信息更贴近失败现场）。

    def collect_material(
        self,
        url: str,
        with_diff: bool = True,
        max_candidates: int = 12,
    ) -> dict[str, Any]:
        """采集素材包（Agent 两段式契约 · 第一段）。

        只做**确定性**的部分：下载 → ASR → 双 ASR diff → 待搜证词提取。
        **不调用任何 LLM、不发起任何联网搜索**——搜证与校正交给宿主智能体
        用它自己的搜索工具与模型完成。

        Args:
            url: 视频 URL
            with_diff: 是否跑 faster-whisper 做对照并产出 diff
            max_candidates: 待搜证词上限

        Returns:
            素材包字典（schema: vidknot.material/1）
        """
        from ..core.agent_material import build_material_bundle
        from ..core.corrector import _make_diff
        from ..core.transcriber import FasterWhisperASR
        from ..utils.config_manager import ConfigManager

        strategy = ConfigManager().get(
            "platforms", "transcription", "strategy", default="subtitle_first"
        )
        audio_path, metadata = self.downloader.download_audio_with_metadata(
            url, force_audio=(strategy != "subtitle_first")
        )

        subtitle_text = metadata.get("subtitle_text")
        if subtitle_text:
            transcription = subtitle_text
        else:
            if audio_path is None:
                audio_path, metadata = self.downloader.download_audio_with_metadata(
                    url, force_audio=True
                )
            transcription = self.transcriber.transcribe(
                audio_path, language=self.language
            )

        fw_segments = ""
        diff_lines: list[str] = []
        if with_diff:
            if audio_path is None:
                # 字幕优先路径拿不到音频（平台已给官方字幕），而 FW 对照必须
                # 有音频 —— 补一次纯音频下载。转写仍用字幕（质量更高且免 ASR）。
                try:
                    audio_path, audio_metadata = (
                        self.downloader.download_audio_with_metadata(
                            url, force_audio=True
                        )
                    )
                    # 保留第一次拿到的元信息（含字幕），只补齐缺失字段
                    for key in ("duration", "title", "uploader", "platform", "id"):
                        if key not in metadata and key in audio_metadata:
                            metadata[key] = audio_metadata[key]
                except Exception as e:
                    logger.warning(f"FW 对照需要音频但下载失败，跳过 diff: {e}")
            if audio_path is not None:
                try:
                    fw_transcriber = FasterWhisperASR()
                    fw_segments = fw_transcriber.transcribe(
                        audio_path, language=self.language
                    )
                    if fw_segments and transcription:
                        diff_lines, _, _ = _make_diff(fw_segments, transcription)
                except Exception as e:
                    logger.warning(f"FW 对照转录失败，跳过 diff: {e}")

        return build_material_bundle(
            url=url,
            metadata=metadata,
            transcription=transcription,
            fw_segments=fw_segments,
            diff_lines=diff_lines,
            max_candidates=max_candidates,
        )

    def save_markdown(
        self,
        url: str,
        markdown: str,
        metadata: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str | list[str]:
        """保存外部生成的 Markdown（Agent 两段式契约 · 第二段）。

        用于「宿主智能体用自己的模型写好笔记后回存」的场景。

        Args:
            url: 视频 URL（写入 frontmatter 的 source）
            markdown: 笔记正文
            metadata: 元信息（title/author/duration/platform…）；可由素材包带入
            options: 保存选项（tags/feishu_folder/…）

        Returns:
            保存位置列表或单一位置
        """
        metadata = metadata or {}
        result = {
            "title": metadata.get("title") or "视频笔记",
            "author": metadata.get("author", ""),
            "duration": metadata.get("duration", 0),
            "source_url": metadata.get("source_url") or url,
            "source_platform": metadata.get("source_platform", ""),
            "markdown": markdown or "",
            "transcription": metadata.get("transcription", ""),
        }
        return self.save(result, options)

    def run(self, url: str) -> dict[str, Any]:
        """
        执行完整处理管道（同步）

        Args:
            url: 视频 URL

        Returns:
            处理结果字典
        """
        if self.cache:
            cached = self.cache.get(url, self.format)
            if cached:
                cached["cache_hit"] = True
                return cached

        from ..utils.config_manager import ConfigManager

        strategy = ConfigManager().get(
            "platforms", "transcription", "strategy", default="subtitle_first"
        )
        audio_path, metadata = self.downloader.download_audio_with_metadata(
            url, force_audio=(strategy != "subtitle_first")
        )

        subtitle_text = metadata.get("subtitle_text")
        if subtitle_text:
            # 字幕优先：平台已提供官方字幕，跳过 ASR
            transcription = subtitle_text
        else:
            if audio_path is None:
                audio_path, metadata = self.downloader.download_audio_with_metadata(
                    url, force_audio=True
                )
            transcription = self.transcriber.transcribe(
                audio_path,
                language=self.language,
            )

        result = {
            "title": metadata.get("title", "未知标题"),
            "author": metadata.get("uploader", "未知作者"),
            "duration": metadata.get("duration", 0),
            "source_url": url,
            "source_platform": metadata.get("platform", "unknown"),
            "transcription": transcription,
            "metadata": metadata,
            "cache_hit": False,
        }

        if self.format == "structured":
            from ..core.processor import resolve_markdown

            processed = self.processor.summarize(transcription, metadata)
            markdown = resolve_markdown(processed.get("markdown"), transcription)
            if not (processed.get("markdown") or "").strip():
                # LLM 只返回了推理内容（响应被 max_tokens 截断），回退到原始转录
                logger.warning("LLM 未返回有效笔记内容，回退到原始转录文本")
            result["markdown"] = markdown
            # 结构化 JSON（供下游 Agent 消费；LLM 失败时回退最小结构）
            try:
                result["structured"] = self.processor.extract_structured(
                    transcription, metadata
                )
                result["structured"]["segments"] = metadata.get("subtitle_segments", [])
            except Exception as e:
                logger.warning(f"结构化 JSON 提取失败: {e}")
                result["structured"] = {
                    "segments": metadata.get("subtitle_segments", []),
                    "topics": [],
                    "entities": [],
                    "key_points": [],
                    "summary_one_line": "",
                    "tags": [],
                }
        else:
            result["markdown"] = transcription

        if self.cache:
            self.cache.set(url, self.format, result)

        return result

    def run_batch(
        self,
        urls: list[str],
        max_workers: int = 3,
        save_options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        批量处理多个视频 URL（线程池并发，默认 max_workers=3）

        Args:
            urls: 视频 URL 列表
            max_workers: 最大并发数
            save_options: 保存选项（非 None 时逐个保存到目的地）

        Returns:
            结果列表，每项含 url/success 字段，失败项含 error
        """
        from concurrent.futures import ThreadPoolExecutor

        def _run_one(url: str) -> dict[str, Any]:
            try:
                result = self.run(url)
                result["url"] = url
                result["success"] = True
                if save_options is not None and self.destination != "none":
                    saved = self.save(result, save_options)
                    result["saved_to"] = saved
                return result
            except Exception as e:
                logger.error(f"批量处理失败 {url}: {e}")
                return {"url": url, "success": False, "error": str(e)}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(_run_one, urls))

    def save(
        self,
        result: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> str | list[str]:
        """
        保存结果到目的地（同步）

        v0.6.13 修复：此前写入器只在传入**非空** config 时才被实例化，
        CLI 传的空 dict（falsy）与 MCP 完全不传，都会让写入器变成 ``None``，
        结果 ``save()`` 静默返回空串 —— 保存链路实际从未生效且不报错。
        现在写入器一律惰性构造，凭证缺失会明确抛错。

        Args:
            result: 处理结果
            options: 保存选项

        Returns:
            保存位置列表或单一位置；无保存目的地时返回空字符串

        Raises:
            StorageError: 任一请求的目的地保存失败
        """
        options = options or {}
        saved: list[str] = []
        errors: list[tuple[str, Exception]] = []

        # 标签键名兼容：CLI/MCP 历史上传的是 obsidian_tags，save_note 用 tags
        tags = options.get("tags") or options.get("obsidian_tags") or []

        markdown = result.get("markdown", result.get("transcription", ""))
        metadata = {
            "title": result.get("title", "视频笔记"),
            "author": result.get("author", ""),
            "duration": result.get("duration", 0),
            "source_url": result.get("source_url", ""),
            "source_platform": result.get("source_platform", ""),
            "tags": tags,
        }

        def _attempt(label: str, action):
            """执行单个目的地的保存；失败只记录，不影响其他目的地。"""
            try:
                location = action()
            except Exception as e:  # noqa: BLE001 - 汇总后统一抛出
                errors.append((label, e))
                logger.error(f"{label} 保存失败: {e}")
            else:
                saved.append(f"{label}: {location}")

        if self.destination in ("feishu", "both"):
            _attempt(
                "飞书",
                lambda: self._get_feishu_writer().create_document(
                    title=metadata["title"],
                    markdown_content=markdown,
                    folder_name=options.get("feishu_folder"),
                ),
            )

        if self.destination in ("yuque", "both"):
            _attempt(
                "语雀",
                lambda: self._get_yuque_writer().create_document(
                    title=metadata["title"],
                    markdown_content=markdown,
                    path=options.get("yuque_path"),
                ),
            )

        if self.destination in ("notion", "both"):
            _attempt(
                "Notion",
                lambda: self._get_notion_writer().create_page(
                    title=metadata["title"],
                    markdown_content=markdown,
                    parent_id=options.get("notion_parent_id"),
                ),
            )

        if self.destination in ("obsidian", "both"):
            _attempt(
                "Obsidian",
                lambda: self._get_obsidian_writer().save_note(
                    markdown_content=markdown,
                    metadata=metadata,
                    tags=tags,
                ),
            )

        if errors:
            # 单一失败时原样抛出（保留 FeishuAuthError 等具体子类与 hint）
            if len(errors) == 1:
                raise errors[0][1]
            raise StorageError(
                "笔记保存失败：" + "；".join(f"{lb}: {e}" for lb, e in errors),
                details=("已成功保存：" + "；".join(saved)) if saved else None,
                hint="请检查各目的地的凭证与网络连通性（vidknot --check-env 可查环境）",
            )

        if not saved:
            return ""
        if len(saved) == 1:
            return saved[0]
        return saved

    # ===== 写入器惰性构造 =====

    def _writer_config(self, kind: str) -> dict[str, Any]:
        """解析某个目的地的写入器参数。

        优先级：显式传入的 config > config.yaml > 写入器自身的环境变量默认值。
        config.yaml 里的占位符（``YOUR_XXX``）会被忽略，避免把占位符
        当成真实凭证传下去。

        Args:
            kind: obsidian / feishu / notion / yuque

        Returns:
            写入器构造参数
        """
        from ..utils.config_manager import ConfigManager

        config = ConfigManager()
        kwargs: dict[str, Any] = {}

        if kind == "obsidian":
            section = config.get("obsidian") or {}
            vault_path = section.get("vault_path")
            if vault_path and not _is_placeholder(vault_path):
                kwargs["vault_path"] = vault_path
            default_folder = section.get("default_folder")
            if default_folder and not _is_placeholder(default_folder):
                kwargs["default_folder"] = default_folder
            auto_create = section.get("auto_create")
            if auto_create is not None:
                kwargs["auto_create_folders"] = _as_bool(auto_create)
            return kwargs

        if kind == "feishu":
            section = config.get("feishu") or {}
            for cfg_key, arg_name in (
                ("api_key", "api_key"),
                ("app_id", "app_id"),
                ("app_secret", "app_secret"),
                ("default_folder", "default_folder"),
                ("wiki_node", "wiki_node_id"),
            ):
                value = section.get(cfg_key)
                if value and not _is_placeholder(value):
                    kwargs[arg_name] = value
            return kwargs

        if kind == "notion":
            section = config.get("notion") or {}
            token = section.get("token")
            if token and not _is_placeholder(token):
                kwargs["token"] = token
            page_id = section.get("page_id")
            if page_id and not _is_placeholder(page_id):
                kwargs["parent_page_id"] = page_id
            database_id = section.get("database_id")
            if database_id and not _is_placeholder(database_id):
                kwargs["database_id"] = database_id
            return kwargs

        # yuque
        section = config.get("yuque") or {}
        for cfg_key, arg_name in (
            ("token", "token"),
            ("login", "login"),
            ("default_path", "default_path"),
        ):
            value = section.get(cfg_key)
            if value and not _is_placeholder(value):
                kwargs[arg_name] = value
        return kwargs

    def _make_writer(self, kind: str, writer_cls, config: dict | None):
        """构造写入器；凭证缺失时抛出可操作的 StorageError。

        Args:
            kind: 目的地标识（用于错误提示）
            writer_cls: 写入器类
            config: 显式传入的配置（None 时回落到 config.yaml）

        Returns:
            写入器实例
        """
        kwargs = dict(config) if config else self._writer_config(kind)
        kwargs = {k: v for k, v in kwargs.items() if not _is_placeholder(v)}
        try:
            return writer_cls(**kwargs)
        except NoAPIKeyError as e:
            raise StorageError(
                f"{_DESTINATION_LABELS.get(kind, kind)} 凭证缺失，笔记未保存",
                details=e.message,
                hint=e.hint,
            ) from e

    def _get_feishu_writer(self) -> FeishuWriter:
        """获取飞书写入器（延迟初始化）"""
        if self._feishu is None:
            self._feishu = self._make_writer(
                "feishu", FeishuWriter, self._feishu_config
            )
        return self._feishu

    def _get_obsidian_writer(self) -> ObsidianWriter:
        """获取 Obsidian 写入器（延迟初始化）"""
        if self._obsidian is None:
            self._obsidian = self._make_writer(
                "obsidian", ObsidianWriter, self._obsidian_config
            )
        return self._obsidian

    def _get_yuque_writer(self) -> YuqueWriter:
        """获取语雀写入器（延迟初始化）"""
        if self._yuque is None:
            self._yuque = self._make_writer("yuque", YuqueWriter, self._yuque_config)
        return self._yuque

    def _get_notion_writer(self) -> NotionWriter:
        """获取 Notion 写入器（延迟初始化）"""
        if self._notion is None:
            self._notion = self._make_writer(
                "notion", NotionWriter, self._notion_config
            )
        return self._notion
