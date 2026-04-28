"""
VidkNot 配置管理器

加载和管理 config.yaml 配置文件
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .exceptions import ConfigError


class ConfigManager:
    """
    配置管理器

    支持多层级配置（优先级从低到高）：
    1. 默认配置 (代码中)
    2. 配置文件 (config.yaml / config.local.yaml)
    3. 环境变量 (优先级最高)
    """

    _instance = None

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        self._initialized = True
        # 确保 _config_path 为 Path 对象（支持 .exists() 等方法）
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = self._find_config_path()
        self._config = self._load_config()

    def _find_config_path(self) -> Optional[Path]:
        """
        按优先级查找配置文件

        优先级: config.local.yaml > config.yaml > ~/.vidknot/config.yaml
        """
        candidates = [
            Path.cwd() / "config.local.yaml",  # 用户本地覆盖优先
            Path.cwd() / "config.yaml",
            Path(__file__).parent.parent.parent / "config.yaml",
            Path.home() / ".vidknot" / "config.yaml",
        ]

        for path in candidates:
            if path.exists():
                return path

        return None

    def _load_config(self) -> Dict[str, Any]:
        """加载并合并配置"""
        config = self._default_config()

        if self._config_path and self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
                    config = self._deep_merge(config, user_config)
            except yaml.YAMLError as e:
                raise ConfigError(
                    f"配置文件格式错误: {self._config_path}",
                    details=str(e),
                )
            except OSError as e:
                raise ConfigError(
                    f"读取配置文件失败: {self._config_path}",
                    details=str(e),
                )

        # 应用环境变量覆盖（最高优先级）
        config = self._apply_env_overrides(config)

        return config

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "settings": {
                "language": "auto",
                "output_dir": "./notes",
                "stt_preference": "local",  # local / siliconflow
                "default_destination": "obsidian",
            },
            "local_whisper": {
                "model_size": "turbo",
                "device": "auto",
                "compute_type": "int8",
            },
            "siliconflow_asr": {
                "model": "FunAudioLLM/SenseVoiceSmall",
            },
            "providers": {
                "default_provider": "openai",
                "openai": {
                    "api_key": None,
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4o",
                    "max_tokens": 4000,
                },
                "zhipuai": {
                    "api_key": None,
                    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                    "model": "glm-4",
                    "max_tokens": 4000,
                },
                "siliconflow": {
                    "api_key": None,
                    "base_url": "https://api.siliconflow.cn/v1",
                    "model": "deepseek-ai/DeepSeek-V3",
                    "max_tokens": 4000,
                },
            },
            "feishu": {
                "api_key": None,
                "app_id": None,
                "app_secret": None,
                "default_folder": "VidkNot 笔记",
                "wiki_node": None,
            },
            "obsidian": {
                "vault_path": None,
                "default_folder": "视频笔记",
                "auto_create": True,
            },
            "douyin": {
                "enable_third_party": False,
                "enable_cdp": True,
                "enable_browser_cookie3": True,
                "cookie_file": None,
                "tikhub": {
                    "api_key": None,
                },
                "third_party_apis": None,
            },
        }

    def _deep_merge(self, default: Dict, user: Dict) -> Dict:
        """深度合并配置（user 覆盖 default）"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _apply_env_overrides(self, config: Dict) -> Dict:
        """应用环境变量覆盖（最高优先级）"""
        env_mappings = {
            # OpenAI
            "OPENAI_API_KEY": ("providers", "openai", "api_key"),
            "OPENAI_BASE_URL": ("providers", "openai", "base_url"),
            "OPENAI_MODEL": ("providers", "openai", "model"),
            # 智谱 AI
            "ZHIPUAI_API_KEY": ("providers", "zhipuai", "api_key"),
            "ZHIPUAI_BASE_URL": ("providers", "zhipuai", "base_url"),
            "ZHIPUAI_MODEL": ("providers", "zhipuai", "model"),
            # 飞书
            "FEISHU_API_KEY": ("feishu", "api_key"),
            "FEISHU_APP_ID": ("feishu", "app_id"),
            "FEISHU_APP_SECRET": ("feishu", "app_secret"),
            "FEISHU_FOLDER": ("feishu", "default_folder"),
            "FEISHU_WIKI_NODE": ("feishu", "wiki_node"),
            # Obsidian
            "OBSIDIAN_VAULT_PATH": ("obsidian", "vault_path"),
            "OBSIDIAN_FOLDER": ("obsidian", "default_folder"),
            # 全局设置
            "VIDKNOT_LANGUAGE": ("settings", "language"),
            "VIDKNOT_DESTINATION": ("settings", "default_destination"),
            "VIDKNOT_MODEL_SIZE": ("local_whisper", "model_size"),
            "VIDKNOT_DEVICE": ("local_whisper", "device"),
            "VIDKNOT_MAX_TOKENS": ("providers", "openai", "max_tokens"),
            # ASR 提供者
            "VIDKNOT_STT_PREFERENCE": ("settings", "stt_preference"),
            # 硅基流动
            "SILICONFLOW_API_KEY": ("providers", "siliconflow", "api_key"),
            # 抖音
            "VIDKNOT_DOUYIN_COOKIE_FILE": ("douyin", "cookie_file"),
            "VIDKNOT_DOUYIN_ENABLE_THIRD_PARTY": ("douyin", "enable_third_party"),
            "TIKHUB_API_KEY": ("douyin", "tikhub", "api_key"),
        }

        for env_var, path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                current = config
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = value

        return config

    def get(self, *keys, default=None) -> Any:
        """
        获取配置值

        Args:
            *keys: 配置路径，如 get("providers", "openai", "model")
            default: 默认值（配置不存在时返回）

        Returns:
            配置值或默认值
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def get_provider(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取 LLM 提供商配置"""
        name = name or self.get("providers", "default_provider")
        return self.get("providers", name) or {}

    def get_feishu_config(self) -> Dict[str, Any]:
        """获取飞书配置"""
        return self.get("feishu") or {}

    def get_obsidian_config(self) -> Dict[str, Any]:
        """获取 Obsidian 配置"""
        return self.get("obsidian") or {}

    def get_douyin_config(self) -> Dict[str, Any]:
        """获取抖音下载配置（含布尔值转换）"""
        raw = self.get("douyin") or {}
        # 环境变量传入的都是字符串，需要转换布尔值
        for key in ("enable_third_party", "enable_cdp", "enable_browser_cookie3"):
            if key in raw and isinstance(raw[key], str):
                raw[key] = raw[key].lower() in ("true", "1", "yes", "on")
        return raw

    def reload(self):
        """重新加载配置（从文件重新读取 + 应用环境变量）"""
        self._config = self._load_config()

    def save(self, save_path: Optional[str] = None) -> Path:
        """
        保存当前配置到文件

        Args:
            save_path: 保存路径，None=覆盖原配置文件

        Returns:
            保存的文件路径
        """
        if save_path:
            path = Path(save_path)
        elif self._config_path:
            # ✅ 修复：覆盖原配置文件（而不是创建新文件）
            path = self._config_path
        else:
            # 没有原路径，创建到当前目录
            path = Path.cwd() / "config.yaml"

        path.parent.mkdir(parents=True, exist_ok=True)

        # 使用 YAML 保留格式的输出
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._config,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        self._config_path = path
        return path

    def validate_required(self, *required_keys) -> List[str]:
        """
        验证必填配置

        Args:
            *required_keys: 必填配置路径，如 validate_required(("feishu", "app_id"))

        Returns:
            缺失的配置路径列表（空=全部通过）
        """
        missing = []
        for keys in required_keys:
            value = self.get(*keys)
            if value is None or value == "":
                missing.append(".".join(str(k) for k in keys))
        return missing
