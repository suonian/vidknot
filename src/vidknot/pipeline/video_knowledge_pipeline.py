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
from ..utils.exceptions import StorageError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VideoKnowledgePipeline:
    """
    视频知识处理管道

    接收视频 URL，执行完整的处理流程：
    1. 下载音频
    2. 云端 ASR 转录（SiliconFlow SenseVoice）
    3. LLM 生成笔记
    4. 路由到目的地（飞书/语雀/Notion/Obsidian）
    """

    SUPPORTED_DESTINATIONS = ["feishu", "yuque", "notion", "obsidian", "both", "none"]

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
        if yuque_config:
            self._yuque = YuqueWriter(**yuque_config)
        if notion_config:
            self._notion = NotionWriter(**notion_config)

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
            processed = self.processor.summarize(transcription, metadata)
            result["markdown"] = processed["markdown"]
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

        Args:
            result: 处理结果
            options: 保存选项

        Returns:
            保存位置列表或单一位置
        """
        options = options or {}
        saved = []

        markdown = result.get("markdown", result.get("transcription", ""))
        metadata = {
            "title": result.get("title", "视频笔记"),
            "author": result.get("author", ""),
            "duration": result.get("duration", 0),
            "source_url": result.get("source_url", ""),
            "source_platform": result.get("source_platform", ""),
            "tags": options.get("tags", []),
        }

        if self.destination in ("feishu", "both"):
            feishu = self._get_feishu_writer()
            if feishu:
                try:
                    url = feishu.create_document(
                        title=metadata["title"],
                        markdown_content=markdown,
                        folder_name=options.get("feishu_folder"),
                    )
                    saved.append(f"飞书: {url}")
                except StorageError as e:
                    logger.error(f"飞书保存失败: {e}")
                    raise

        if self.destination in ("yuque", "both"):
            yuque = self._get_yuque_writer()
            if yuque:
                try:
                    url = yuque.create_document(
                        title=metadata["title"],
                        markdown_content=markdown,
                        path=options.get("yuque_path"),
                    )
                    saved.append(f"语雀: {url}")
                except StorageError as e:
                    logger.error(f"语雀保存失败: {e}")
                    raise

        if self.destination in ("notion", "both"):
            notion = self._get_notion_writer()
            if notion:
                try:
                    url = notion.create_page(
                        title=metadata["title"],
                        markdown_content=markdown,
                        parent_id=options.get("notion_parent_id"),
                    )
                    saved.append(f"Notion: {url}")
                except StorageError as e:
                    logger.error(f"Notion 保存失败: {e}")
                    raise

        if self.destination in ("obsidian", "both"):
            obsidian = self._get_obsidian_writer()
            if obsidian:
                try:
                    path = obsidian.save_note(
                        markdown_content=markdown,
                        metadata=metadata,
                        tags=options.get("tags", []),
                    )
                    saved.append(f"Obsidian: {path}")
                except StorageError as e:
                    logger.error(f"Obsidian 保存失败: {e}")
                    raise

        if not saved:
            return ""
        if len(saved) == 1:
            return saved[0]
        return saved

    def _get_feishu_writer(self) -> FeishuWriter | None:
        """获取飞书写入器（延迟初始化）"""
        if self._feishu is None and self._feishu_config:
            self._feishu = FeishuWriter(**self._feishu_config)
        return self._feishu

    def _get_obsidian_writer(self) -> ObsidianWriter | None:
        """获取 Obsidian 写入器（延迟初始化）"""
        if self._obsidian is None and self._obsidian_config:
            self._obsidian = ObsidianWriter(**self._obsidian_config)
        return self._obsidian

    def _get_yuque_writer(self) -> YuqueWriter | None:
        """获取语雀写入器（延迟初始化）"""
        if self._yuque is None and self._yuque_config:
            self._yuque = YuqueWriter(**self._yuque_config)
        return self._yuque

    def _get_notion_writer(self) -> NotionWriter | None:
        """获取 Notion 写入器（延迟初始化）"""
        if self._notion is None and self._notion_config:
            self._notion = NotionWriter(**self._notion_config)
        return self._notion
