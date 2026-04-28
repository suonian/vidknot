"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot FastAPI 服务

提供 REST API 接口，支持:
- 视频转录 + 笔记生成
- 飞书/Obsidian 存储路由
- MCP Tool 元数据
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

from .pipeline.video_knowledge_pipeline import VideoKnowledgePipeline
from .utils.env_check import check_ffmpeg, check_all_requirements
from .utils.logger import get_logger

logger = get_logger("vidknot.api")

app = FastAPI(
    title="VidkNot API",
    description="Video Knowledge, Knotted. 将视频链接转换为结构化笔记。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranscribeRequest(BaseModel):
    url: str = Field(..., description="视频 URL")
    mode: str = Field(default="summary", description="raw(仅转录) / summary(结构化笔记)")
    language: str = Field(default="auto", description="语言: auto/zh/en/ja/ko")
    destination: str = Field(default="obsidian", description="保存目的地: feishu/obsidian/both/none")
    feishu_folder: Optional[str] = Field(default=None, description="飞书文件夹名称")
    obsidian_tags: List[str] = Field(default_factory=list, description="Obsidian 标签")
    use_cache: bool = Field(default=True, description="是否使用缓存")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("raw", "summary"):
            raise ValueError("mode 必须为 raw 或 summary")
        return v

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, v: str) -> str:
        if v not in ("feishu", "obsidian", "both", "none"):
            raise ValueError("destination 必须为 feishu/obsidian/both/none")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("auto", "zh", "en", "ja", "ko"):
            raise ValueError("language 必须为 auto/zh/en/ja/ko")
        return v


class TranscribeResponse(BaseModel):
    success: bool
    title: Optional[str] = None
    author: Optional[str] = None
    duration: Optional[int] = None
    source_url: str
    transcription: str
    markdown: Optional[str] = None
    cache_hit: bool = False
    saved_to: Optional[List[str]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    ffmpeg_ok: bool
    ffmpeg_path: Optional[str] = None
    checks_passed: bool


class ToolMetadata(BaseModel):
    name: str
    description: str
    inputSchema: dict


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health():
    """健康检查"""
    all_ok, messages = check_all_requirements()
    ffmpeg_ok, ffmpeg_path = check_ffmpeg()

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        ffmpeg_ok=ffmpeg_ok,
        ffmpeg_path=ffmpeg_path,
        checks_passed=all_ok,
    )


@app.post("/transcribe", response_model=TranscribeResponse, tags=["转录"])
async def transcribe(req: TranscribeRequest):
    """视频转录 + 笔记生成"""
    from .utils.exceptions import (
        DownloadError,
        TranscriptionError,
        LLMError,
        StorageError,
        DependencyError,
    )

    try:
        pipeline = VideoKnowledgePipeline(
            destination=req.destination,
            format=req.mode,
            language=req.language,
        )

        result = pipeline.run(req.url)

        saved_to = None
        if req.destination != "none":
            saved = pipeline.save(result, {
                "feishu_folder": req.feishu_folder,
                "obsidian_tags": req.obsidian_tags,
            })
            saved_to = saved if isinstance(saved, list) else [saved]

        return TranscribeResponse(
            success=True,
            title=result.get("title"),
            author=result.get("author"),
            duration=result.get("duration"),
            source_url=req.url,
            transcription=result.get("transcription", ""),
            markdown=result.get("markdown"),
            cache_hit=result.get("cache_hit", False),
            saved_to=saved_to,
        )

    except DependencyError as e:
        logger.error(f"环境错误: {e}")
        raise HTTPException(status_code=503, detail=f"环境配置错误: {e.message}")

    except DownloadError as e:
        logger.error(f"下载错误: {e}")
        raise HTTPException(status_code=502, detail=f"下载失败: {e.message}")

    except TranscriptionError as e:
        logger.error(f"转录错误: {e}")
        raise HTTPException(status_code=502, detail=f"转录失败: {e.message}")

    except LLMError as e:
        logger.error(f"LLM 错误: {e}")
        raise HTTPException(status_code=502, detail=f"笔记生成失败: {e.message}")

    except StorageError as e:
        logger.error(f"存储错误: {e}")
        raise HTTPException(status_code=502, detail=f"保存失败: {e.message}")

    except Exception as e:
        logger.exception(f"未知错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools/metadata", response_model=ToolMetadata, tags=["元数据"])
async def get_tool_metadata():
    """获取 MCP Tool 元数据"""
    from .adapters.agent_bridge import get_tool_metadata
    meta = get_tool_metadata()
    return ToolMetadata(
        name=meta["function"]["name"],
        description=meta["function"]["description"],
        inputSchema=meta["function"]["parameters"],
    )


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {
        "name": "VidkNot API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# -----------------------------------------------------------------------------
# VidkNot - Video Knowledge, Knotted.
# -----------------------------------------------------------------------------
# Copyright (c) 2026 VidkNot Team
# 
# This software is licensed under the MIT License.
# See LICENSE file in the project root for details.
# 
# Repository: https://github.com/suonian/vidknot
# -----------------------------------------------------------------------------

