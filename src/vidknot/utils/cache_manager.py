"""
VidkNot 缓存管理器

基于 MD5 的缓存系统，避免重复下载和转录
"""

import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any


class CacheManager:
    """
    缓存管理器

    - 键: MD5(url + mode)
    - 位置: ./cache/
    - 有效期: 30 天
    - 类型: 转录结果 JSON + 音频文件
    """

    def __init__(self, cache_dir: str = "./.vidknot_cache", max_age_days: int = 30):
        self.cache_dir = Path(cache_dir)
        self.max_age_days = max_age_days
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str, mode: str = "summary") -> str:
        """生成缓存键"""
        key_str = f"{url}_{mode}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, url: str, mode: str = "summary") -> Optional[Dict[str, Any]]:
        """
        获取缓存

        Args:
            url: 视频 URL
            mode: 处理模式 (summary/raw)

        Returns:
            缓存数据或 None
        """
        cache_key = self._get_cache_key(url, mode)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        # 检查是否过期
        cache_age = time.time() - cache_path.stat().st_mtime
        max_age_seconds = self.max_age_days * 24 * 3600

        if cache_age > max_age_seconds:
            # 过期，删除
            cache_path.unlink()
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
                data["cache_hit"] = True
                return data
        except Exception:
            return None

    def set(self, url: str, mode: str, data: Dict[str, Any]) -> bool:
        """
        设置缓存

        Args:
            url: 视频 URL
            mode: 处理模式
            data: 要缓存的数据

        Returns:
            是否成功
        """
        cache_key = self._get_cache_key(url, mode)
        cache_path = self._get_cache_path(cache_key)

        try:
            # 移除内部字段
            cache_data = {k: v for k, v in data.items() if not k.startswith("_")}

            # 添加元数据
            cache_data["_cached_at"] = datetime.now().isoformat()
            cache_data["_cache_url"] = url
            cache_data["_cache_mode"] = mode

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception:
            return False

    def delete(self, url: str, mode: str = "summary") -> bool:
        """删除缓存"""
        cache_key = self._get_cache_key(url, mode)
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            cache_path.unlink()
            return True
        return False

    def clear(self, max_age_days: Optional[int] = None) -> int:
        """
        清理过期缓存

        Args:
            max_age_days: 超过此天数的缓存将被删除

        Returns:
            删除的缓存数量
        """
        max_age = max_age_days or self.max_age_days
        max_age_seconds = max_age * 24 * 3600
        removed = 0

        for cache_file in self.cache_dir.glob("*.json"):
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age > max_age_seconds:
                cache_file.unlink()
                removed += 1

        return removed

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        # 统计过期缓存
        max_age_seconds = self.max_age_days * 24 * 3600
        expired = 0
        for f in cache_files:
            age = time.time() - f.stat().st_mtime
            if age > max_age_seconds:
                expired += 1

        return {
            "total_cached": len(cache_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "expired": expired,
            "active": len(cache_files) - expired,
            "cache_dir": str(self.cache_dir),
            "max_age_days": self.max_age_days,
        }

    def clear_all(self) -> int:
        """清空所有缓存"""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count
