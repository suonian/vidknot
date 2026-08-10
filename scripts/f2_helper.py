#!/usr/bin/env python3
"""
f2_helper.py — VidkNot 抖音下载辅助脚本（基于 f2 X-Bogus 签名）

用法：
    f2_helper.py parse <video_url> [--cookie-file PATH]

输出（stdout JSON）：
    成功: {"ok": true, "video_url": "...", "title": "...", "author": "...", "duration": 0, "aweme_id": "..."}
    失败: {"ok": false, "error": "..."}

设计要点：
- 使用 f2 库的 XBogusManager 自动签名 API 请求（解决抖音 X-Bogus 反爬）
- 不污染 vidknot 主 venv（独立 .venv-f2）
- 输出 JSON 给主程序解析

运行环境：
- 需要安装 f2 的独立虚拟环境（默认 ./../.venv-f2，可在环境变量 F2_VENV 中覆盖）
- 主程序通过 subprocess 调用本脚本
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# 定位 f2 虚拟环境（默认与仓库同级 .venv-f2）
_F2_VENV = os.environ.get("F2_VENV") or str(Path(__file__).resolve().parent.parent / ".venv-f2")
_F2_SITE_PACKAGES = os.path.join(_F2_VENV, "lib", "python3.13", "site-packages")
if Path(_F2_SITE_PACKAGES).exists():
    sys.path.insert(0, _F2_SITE_PACKAGES)

import httpx  # noqa: E402

try:
    from f2.apps.douyin.api import DouyinAPIEndpoints as dyendpoint  # noqa: E402, N813
    from f2.apps.douyin.utils import ClientConfManager, XBogusManager  # noqa: E402
except ImportError as e:
    print(json.dumps({"ok": False, "error": f"f2 未安装或虚拟环境配置错误: {e}"}), flush=True)
    sys.exit(1)


def load_cookie_str(cookie_file: str | None) -> str:
    """从 Netscape 格式 cookie 文件读取为 'key=val; key2=val2' 字符串"""
    if not cookie_file or not Path(cookie_file).exists():
        return ""
    cookies: list[str] = []
    try:
        with open(cookie_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies.append(f"{parts[5]}={parts[6]}")
    except Exception:
        return ""
    return "; ".join(cookies)


async def fetch_aweme_id(url: str, headers: dict) -> str:
    """从短链接或长链接提取 aweme_id"""
    # 1. 如果直接是数字 ID
    if url.strip().isdigit():
        return url.strip()

    # 2. 从长链接直接提取
    match = re.search(r"/(?:video|note)/(\d+)", url)
    if match:
        return match.group(1)

    # 3. 短链接需要 302 重定向
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        final_url = str(resp.url)
        match = re.search(r"/(?:video|note)/(\d+)", final_url)
        if match:
            return match.group(1)
        # 兜底：从 URL 末尾提取
        match = re.search(r"(\d{15,20})", final_url)
        if match:
            return match.group(1)

    raise ValueError(f"无法从 URL 提取 aweme_id: {url}")


async def fetch_post_detail(aweme_id: str, headers: dict, cookie_str: str) -> dict:
    """使用 XBogus 签名获取抖音作品详情"""
    # 1. 构造未签名的 URL（用 str_2_endpoint 而不是 model_2_endpoint，后者在 f2 0.0.1.7 有 bug）
    ua = headers.get("User-Agent", "")
    base_url = dyendpoint.POST_DETAIL.rstrip("/")
    unsigned_url = f"{base_url}?aweme_id={aweme_id}"

    try:
        signed_url = XBogusManager.str_2_endpoint(ua, unsigned_url)
    except Exception:
        # 备用：完整 Web 端参数
        unsigned_url = (
            f"{base_url}?device_platform=webapp&aid=6383&channel=channel_pc_web"
            f"&pc_client_type=1&version_code=190500&version_name=19.5.0"
            f"&cookie_enabled=true&platform_type=PC&aweme_id={aweme_id}"
        )
        signed_url = XBogusManager.str_2_endpoint(ua, unsigned_url)

    # 2. 发起请求
    req_headers = dict(headers)
    if cookie_str:
        req_headers["Cookie"] = cookie_str

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(signed_url, headers=req_headers)
        resp.raise_for_status()
        data = resp.json()

    # 3. 提取关键字段
    aweme_detail = data.get("aweme_detail", {})
    if not aweme_detail:
        # 尝试 status_code 等错误信息
        status_code = data.get("status_code", "unknown")
        if status_code != 0:
            raise ValueError(f"抖音 API 返回错误: status_code={status_code}, msg={data.get('status_msg', '')}")
        raise ValueError("抖音 API 响应中无 aweme_detail 字段")

    video = aweme_detail.get("video", {})
    play_addr = video.get("play_addr", {})
    url_list = play_addr.get("url_list", [])

    # 取第一个，去水印（playwm → play）
    raw_url = url_list[0] if url_list else ""
    video_url = raw_url.replace("playwm", "play") if raw_url else ""

    if not video_url:
        raise ValueError("未找到视频 URL")

    return {
        "video_url": video_url,
        "title": aweme_detail.get("desc", ""),
        "author": aweme_detail.get("author", {}).get("nickname", ""),
        "duration": video.get("duration", 0) // 1000,  # ms → s
        "aweme_id": aweme_id,
        "cover": video.get("cover", {}).get("url_list", [""])[0] if video.get("cover") else "",
    }


async def main_async(url: str, cookie_file: str | None) -> dict:
    headers = ClientConfManager.headers()
    cookie_str = load_cookie_str(cookie_file)

    # 1. 提取 aweme_id
    aweme_id = await fetch_aweme_id(url, headers)

    # 2. 获取视频详情
    result = await fetch_post_detail(aweme_id, headers, cookie_str)
    return result


def main():
    parser = argparse.ArgumentParser(description="VidkNot 抖音下载辅助（f2 X-Bogus 签名）")
    parser.add_argument("url", help="抖音视频 URL 或 aweme_id")
    parser.add_argument("--cookie-file", help="Netscape 格式 Cookie 文件路径")
    args = parser.parse_args()

    try:
        result = asyncio.run(main_async(args.url, args.cookie_file))
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:500]}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
