"""
VidkNot 配置管理器

加载和管理 config.yaml 配置文件。

支持多层级配置（优先级从低到高）：
1. 默认配置 (代码中)
2. 配置文件 (config.yaml / config.local.yaml)
3. 共享 .env 文件 (VIDKNOT_ENV_FILE 指定，通用 OPENAI_* 键被剥离)
4. 本地 .env 文件 (项目目录 / 当前目录)
5. 进程环境变量 (最高优先级)

共享 .env 文件设计（用于多 agent 宿主）：
- 设置 VIDKNOT_ENV_FILE=~/.hermes/.env 可引入宿主 agent 的 credential 文件
- 该文件中通用的 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL / ZHIPUAI_MODEL
  会被自动剥离，避免宿主 agent 的 key 意外注入 VidkNot 的 provider 配置
- 本地 .env 和进程环境变量不受此限制，所有键均可覆盖
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

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

    def __new__(cls, config_path: str | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str | None = None):
        if self._initialized:
            return

        self._initialized = True
        # 确保 _config_path 为 Path 对象（支持 .exists() 等方法）
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = self._find_config_path()

        # --- .env 加载（dotenv_values，不污染 os.environ）---
        self._dotenv: dict[str, str] = {}

        # 1) VIDKNOT_ENV_FILE：共享 credential 文件（如 ~/.hermes/.env）
        shared_files = [
            p.strip() for p in os.getenv("VIDKNOT_ENV_FILE", "").split(",") if p.strip()
        ]
        for sf in shared_files:
            sf_path = Path(sf).expanduser()
            if sf_path.exists():
                shared_vals = dotenv_values(str(sf_path))
                # 剥离通用 OPENAI_* / ZHIPUAI_MODEL，避免宿主 agent 的 key
                # 意外注入 VidkNot provider 配置
                for k in (
                    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
                    "ZHIPUAI_MODEL",
                ):
                    shared_vals.pop(k, None)
                self._dotenv.update(shared_vals)

        # 2) 本地 .env（项目配置目录 + 当前工作目录，后者覆盖前者）
        config_dir = self._config_path.parent if self._config_path else Path.cwd()
        for env_path in (config_dir / ".env", Path.cwd() / ".env"):
            if env_path.exists():
                self._dotenv.update(dotenv_values(str(env_path)))

        self._config = self._load_config()

    def _find_config_path(self) -> Path | None:
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

    def _load_config(self) -> dict[str, Any]:
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

    def _default_config(self) -> dict[str, Any]:
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
                "openai-compatible": {
                    "api_key": None,
                    "base_url": None,
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

    def _deep_merge(self, default: dict, user: dict) -> dict:
        """深度合并配置（user 覆盖 default）"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _apply_env_overrides(self, config: dict) -> dict:
        """应用环境变量覆盖（最高优先级，含 .env dotenv 文件）"""
        # 单目标映射（env_var -> (path, ...)）
        env_single = {
            # OpenAI (process env only — 不在 .env 中读取，避免与 LLM_API_KEY 冲突)
            "OPENAI_API_KEY": ("providers", "openai", "api_key"),
            "OPENAI_BASE_URL": ("providers", "openai", "base_url"),
            # 智谱 AI
            "ZHIPUAI_API_KEY": ("providers", "zhipuai", "api_key"),
            "ZHIPUAI_BASE_URL": ("providers", "zhipuai", "base_url"),
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
            # OpenAI-compatible provider（通用 LLM 接入点）
            "LLM_BASE_URL": ("providers", "openai-compatible", "base_url"),
            "VIDKNOT_LLM_MODEL": ("providers", "openai-compatible", "model"),
        }

        # OPENAI_API_KEY / OPENAI_BASE_URL: 仅从进程环境变量读取
        # （.env 里同一变量可能属于宿主 agent，不走 dotenv 以免误注入）
        _process_only = {"OPENAI_API_KEY", "OPENAI_BASE_URL"}

        for env_var, path in env_single.items():
            value = os.getenv(env_var)
            if value is None and env_var not in _process_only:
                value = self._dotenv.get(env_var)
            if value is not None:
                current = config
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = value

        # LLM_API_KEY: 同时映射到 openai 和 openai-compatible（向后兼容）
        llm_key = os.getenv("LLM_API_KEY") or self._dotenv.get("LLM_API_KEY")
        if llm_key:
            for provider_name in ("openai", "openai-compatible"):
                target = config.setdefault("providers", {}).setdefault(provider_name, {})
                if not target.get("api_key"):
                    target["api_key"] = llm_key

        # OPENAI_MODEL / ZHIPUAI_MODEL: 仅在默认配置路径下从 dotenv 读取
        # （显式指定 config_path= 的场景说明调用方已完全控制配置，不需这项兼容）
        if self._config_path is None or self._config_path == self._find_config_path():
            for env_var, path in {
                "OPENAI_MODEL": ("providers", "openai", "model"),
                "ZHIPUAI_MODEL": ("providers", "zhipuai", "model"),
            }.items():
                value = os.getenv(env_var) or self._dotenv.get(env_var)
                if value is not None:
                    current = config
                    for key in path[:-1]:
                        current = current.setdefault(key, {})
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

    def get_provider(self, name: str | None = None) -> dict[str, Any]:
        """获取 LLM 提供商配置"""
        name = name or self.get("providers", "default_provider")
        return self.get("providers", name) or {}

    def get_feishu_config(self) -> dict[str, Any]:
        """获取飞书配置"""
        return self.get("feishu") or {}

    def get_obsidian_config(self) -> dict[str, Any]:
        """获取 Obsidian 配置"""
        return self.get("obsidian") or {}

    def get_douyin_config(self) -> dict[str, Any]:
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

    def save(self, save_path: str | None = None) -> Path:
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

    def validate_required(self, *required_keys) -> list[str]:
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
