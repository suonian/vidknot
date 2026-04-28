#!/usr/bin/env python3
"""
VidkNot 统一入口

支持三种运行模式:
- CLI: python -m vidknot <url> [--destination feishu|yuque|notion|obsidian|both|none]
- MCP: python -m vidknot --mcp
- FastAPI: uvicorn vidknot.api:app
"""

import sys
import argparse
from pathlib import Path

from .utils.logger import get_logger

logger = get_logger("vidknot.cli")


def main():
    """智能检测运行模式并启动对应服务"""
    parser = argparse.ArgumentParser(
        description="VidkNot — Video Knowledge, Knotted. 将视频链接转换为结构化笔记，自动保存到飞书文档或 Obsidian Vault。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  CLI 模式:   python -m vidknot <url> [--destination feishu|yuque|notion|obsidian|both|none]
  MCP 模式:   python -m vidknot --mcp
  API 模式:   uvicorn vidknot.api:app --reload

示例:
  # 生成笔记并保存到 Obsidian (默认)
  python -m vidknot https://youtube.com/watch?v=xxx

  # 保存到飞书文档
  python -m vidknot https://bilibili.com/video/BVxxx --destination feishu

  # 仅返回笔记内容，不保存
  python -m vidknot https://youtube.com/watch?v=xxx --destination none

  # 启动 MCP Server (用于 OpenClaw / Claude Desktop)
  python -m vidknot --mcp
        """
    )

    # 运行模式参数
    parser.add_argument("--mcp", action="store_true",
                        help="启动 MCP Stdio 模式 (用于 OpenClaw / Claude Desktop)")
    parser.add_argument("--cli", action="store_true",
                        help="强制使用 CLI 模式 (默认自动检测)")
    parser.add_argument("--check-env", action="store_true",
                        help="检查运行环境依赖是否满足")

    # CLI 参数
    parser.add_argument("url", nargs="?",
                        help="视频 URL (CLI 模式)")
    parser.add_argument("--raw", action="store_true",
                        help="仅输出原始转录文本")
    parser.add_argument("--summary", action="store_true",
                        help="生成结构化笔记 (默认)")
    parser.add_argument("--destination", "-d", default="obsidian",
                        choices=["feishu", "yuque", "notion", "obsidian", "both", "none"],
                        help="笔记保存目的地: feishu(飞书)/yuque(语雀)/notion/obsidian(本地)/both(所有)/none(仅返回)")
    parser.add_argument("--language", "-l", default="auto",
                        help="视频语言: auto/zh/en/ja/ko (默认: auto)")
    parser.add_argument("--output", "-o",
                        help="输出文件路径 (当 destination=none 时)")
    parser.add_argument("--no-cache", action="store_true",
                        help="禁用缓存")
    parser.add_argument("--feishu-folder",
                        help="飞书文档保存的文件夹名称")
    parser.add_argument("--obsidian-tags", nargs="+", default=[],
                        help="Obsidian 笔记标签")
    parser.add_argument("--notify", action="store_true", default=True,
                        help="处理完成后发送通知 (通过 OpenClaw 消息回复)")

    args = parser.parse_args()

    # 模式检测优先级: check-env > MCP > CLI (有url) > Help
    if args.check_env:
        from .utils.env_check import check_all_requirements, get_install_guide
        all_ok, messages = check_all_requirements()
        for msg in messages:
            print(msg)
        if not all_ok:
            print("\n" + get_install_guide())
            sys.exit(1)
        print("\n[OK] 所有环境检查通过")
        sys.exit(0)

    if args.mcp:
        # MCP Stdio 模式
        from .adapters.mcp_server import run_mcp_server
        run_mcp_server()

    elif args.url or args.cli:
        # CLI 模式
        if not args.url and args.cli:
            parser.error("CLI 模式需要提供 URL 参数")
        run_cli(args)

    else:
        # 检查是否通过 uvicorn 调用 (FastAPI 模式)
        if "uvicorn" in sys.argv[0] or any("uvicorn" in arg for arg in sys.argv):
            print("启动 FastAPI 模式，请访问 http://localhost:8000/docs")
            return

        parser.print_help()
        sys.exit(1)


def run_cli(args):
    """CLI 模式主逻辑（同步）"""
    from .core.downloader import VideoDownloader
    from .core.transcriber import SiliconFlowASR
    from .core.processor import ContentProcessor
    from .utils.cache_manager import CacheManager
    from .utils.env_check import check_ffmpeg, check_all_requirements
    from .pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

    logger.info("VidkNot v0.1.0 — Video Knowledge, Knotted.")

    # 环境检查
    logger.info("检查运行环境...")
    all_ok, messages = check_all_requirements()
    if not all_ok:
        for msg in messages:
            if "❌" in msg:
                logger.error(msg)
        logger.error("请安装缺失的依赖后重试")
        sys.exit(1)

    ffmpeg_ok, ffmpeg_path = check_ffmpeg()
    logger.info(f"FFmpeg: {ffmpeg_path}")

    # 确定模式
    mode = "raw" if args.raw else "summary"
    destination = args.destination

    url = args.url
    logger.info(f"正在处理: {url}")
    logger.info(f"处理模式: {'结构化笔记' if mode == 'summary' else '原始转录'}")
    logger.info(f"目的地: {destination}")

    # 检查缓存
    cache = CacheManager()
    if not args.no_cache:
        cached = cache.get(url, mode)
        if cached:
            logger.info("命中缓存!")
            result = cached
        else:
            result = process_video(url, mode, args.language)
            cache.set(url, mode, result)
    else:
        result = process_video(url, mode, args.language)

    # 根据目的地路由
    if destination != "none":
        pipeline = VideoKnowledgePipeline(
            destination=destination,
            format=mode,
            language=args.language,
        )
        saved = pipeline.save(result, {
            "feishu_folder": args.feishu_folder,
            "obsidian_tags": args.obsidian_tags,
        })
        logger.info(f"已保存到: {saved}")

    # 输出结果
    if mode == "summary":
        output = result.get("markdown", "")
    else:
        output = result.get("transcription", "")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info(f"结果已保存: {args.output}")
    else:
        print("\n" + "=" * 60)
        print(output)
        print("=" * 60)


def generate_images_markdown(metadata: dict, image_paths: list) -> str:
    """为纯图片内容生成 Markdown"""
    from datetime import date

    title = metadata.get("title", "小红书图片笔记")
    url = metadata.get("url", "")
    image_dir = metadata.get("image_paths", [])

    lines = [
        "---",
        f"title: {title}",
        f"source: {url}",
        f"date: {date.today().isoformat()}",
        f"platform: xiaohongshu",
        f"type: images",
        "---",
        "",
        f"# {title}",
        "",
        f"来源: {url}",
        "",
        f"图片数量: {len(image_paths)} 张",
        "",
        "## 图片列表",
        "",
    ]

    for i, img_path in enumerate(image_paths, 1):
        from pathlib import Path
        filename = Path(img_path).name
        lines.append(f"### 图片 {i}")
        lines.append(f"![图片 {i}]({filename})")
        lines.append("")

    lines.append("---")
    lines.append(f"*图片保存目录: {image_dir[0].rsplit('/', 1)[0] if image_dir else '未知'}*")

    return "\n".join(lines)


def process_video(url: str, mode: str, language: str) -> dict:
    """处理视频的完整流程（同步）"""
    from .core.downloader import VideoDownloader
    from .core.transcriber import SiliconFlowASR
    from .core.processor import ContentProcessor

    logger.info("正在下载...")
    downloader = VideoDownloader()
    file_path, metadata = downloader.download_audio_with_metadata(url)
    logger.info(f"下载完成: {metadata.get('title', 'Unknown')}")

    result = {
        "title": metadata.get("title"),
        "author": metadata.get("uploader"),
        "duration": metadata.get("duration"),
        "source_url": url,
        "transcription": "",
        "metadata": metadata,
    }

    if metadata.get("is_images_only"):
        image_count = metadata.get("image_count", 0)
        image_paths = metadata.get("image_paths", [])
        result["transcription"] = ""
        result["markdown"] = generate_images_markdown(metadata, image_paths)
        result["is_images_only"] = True
        logger.info(f"纯图片笔记: {image_count} 张图片")
        return result

    logger.info("正在转录...")
    transcriber = SiliconFlowASR()
    transcription = transcriber.transcribe(file_path, language=language)
    logger.info(f"转录完成: {len(transcription)} 字符")
    result["transcription"] = transcription

    if mode == "summary":
        logger.info("正在生成结构化笔记...")
        processor = ContentProcessor()
        processed = processor.summarize(transcription, metadata)
        result["markdown"] = processed["markdown"]
        logger.info("笔记生成完成")
    else:
        result["markdown"] = transcription

    return result


if __name__ == "__main__":
    main()