"""
测试 vidknot.utils.config_manager

注意：每个测试都使用独立的临时目录，避免单例状态污染。
"""

import os
import tempfile
from pathlib import Path

import pytest
from vidknot.utils.config_manager import ConfigManager


class TestConfigManagerDefaults:
    """测试默认配置加载（使用临时目录，无配置文件）"""

    def test_singleton(self, tmp_config_path):
        """ConfigManager 应为单例"""
        c1 = ConfigManager(config_path=str(tmp_config_path))
        c2 = ConfigManager(config_path=str(tmp_config_path))
        assert c1 is c2

    def test_default_language(self, tmp_config_path):
        """默认语言应为 auto"""
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("settings", "language") == "auto"

    def test_default_destination(self, tmp_config_path):
        """默认目的地应为 obsidian"""
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("settings", "default_destination") == "obsidian"

    def test_default_whisper_model(self, tmp_config_path):
        """默认 Whisper 模型应为 turbo"""
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("local_whisper", "model_size") == "turbo"

    def test_get_nested_value(self, tmp_config_path):
        c = ConfigManager(config_path=str(tmp_config_path))
        model = c.get("providers", "openai", "model")
        assert model == "gpt-4o"

    def test_get_with_default(self, tmp_config_path):
        """不存在的路径应返回默认值"""
        c = ConfigManager(config_path=str(tmp_config_path))
        result = c.get("nonexistent", "key", default="fallback")
        assert result == "fallback"

    def test_get_provider_config(self, tmp_config_path):
        c = ConfigManager(config_path=str(tmp_config_path))
        openai_config = c.get_provider("openai")
        assert "api_key" in openai_config
        assert "model" in openai_config
        assert openai_config.get("model") == "gpt-4o"

    def test_get_feishu_config(self, tmp_config_path):
        c = ConfigManager(config_path=str(tmp_config_path))
        feishu = c.get_feishu_config()
        assert isinstance(feishu, dict)

    def test_get_obsidian_config(self, tmp_config_path):
        c = ConfigManager(config_path=str(tmp_config_path))
        obsidian = c.get_obsidian_config()
        assert isinstance(obsidian, dict)

    def test_get_douyin_config(self, tmp_config_path):
        """douyin 配置应包含三层 fallback 相关键"""
        c = ConfigManager(config_path=str(tmp_config_path))
        douyin = c.get_douyin_config()
        assert isinstance(douyin, dict)
        assert "enable_third_party" in douyin
        assert "enable_cdp" in douyin
        assert "enable_browser_cookie3" in douyin
        assert "cookie_file" in douyin
        assert "tikhub" in douyin

    def test_get_douyin_config_bool_conversion(self, tmp_config_path, monkeypatch):
        """环境变量的布尔字符串应被正确转换"""
        monkeypatch.setenv("VIDKNOT_DOUYIN_ENABLE_THIRD_PARTY", "true")
        c = ConfigManager(config_path=str(tmp_config_path))
        douyin = c.get_douyin_config()
        assert douyin["enable_third_party"] is True

    def test_validate_required_all_present(self, tmp_config_path):
        c = ConfigManager(config_path=str(tmp_config_path))
        missing = c.validate_required(("settings", "language"))
        assert missing == []

    def test_validate_required_missing(self, tmp_config_path):
        c = ConfigManager(config_path=str(tmp_config_path))
        missing = c.validate_required(("nonexistent", "key"))
        assert len(missing) == 1


class TestConfigSaveAndReload:
    """测试配置保存和重新加载"""

    def test_save_and_reload(self, tmp_config_path):
        """保存配置再重新加载"""
        # 创建 ConfigManager 并修改配置
        c = ConfigManager(config_path=str(tmp_config_path))
        c._config["settings"]["language"] = "zh"

        # 保存到临时文件
        saved_path = c.save()
        assert saved_path.exists()

        # 重新加载（使用新实例，跳过单例缓存）
        ConfigManager._instance = None
        ConfigManager._initialized = False
        c2 = ConfigManager(config_path=str(tmp_config_path))

        assert c2.get("settings", "language") == "zh"


class TestConfigEnvOverrides:
    """测试环境变量覆盖"""

    def test_env_override_openai_api_key(self, tmp_config_path, monkeypatch):
        """OPENAI_API_KEY 应覆盖配置"""
        monkeypatch.setenv("OPENAI_API_KEY", "env-api-key-123")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("providers", "openai", "api_key") == "env-api-key-123"

    def test_env_override_feishu_app_id(self, tmp_config_path, monkeypatch):
        """FEISHU_APP_ID 应覆盖配置"""
        monkeypatch.setenv("FEISHU_APP_ID", "env-feishu-app")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("feishu", "app_id") == "env-feishu-app"

    def test_env_override_obsidian_vault_path(self, tmp_config_path, monkeypatch):
        """OBSIDIAN_VAULT_PATH 应覆盖配置"""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/custom/vault/path")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("obsidian", "vault_path") == "/custom/vault/path"

    def test_env_override_language(self, tmp_config_path, monkeypatch):
        """VIDKNOT_LANGUAGE 应覆盖配置"""
        monkeypatch.setenv("VIDKNOT_LANGUAGE", "zh")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("settings", "language") == "zh"

    def test_env_override_max_tokens(self, tmp_config_path, monkeypatch):
        """VIDKNOT_MAX_TOKENS 应覆盖配置（环境变量均为字符串，由 Consumer 负责转换）"""
        monkeypatch.setenv("VIDKNOT_MAX_TOKENS", "8000")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("providers", "openai", "max_tokens") == "8000"

    def test_env_override_douyin_cookie_file(self, tmp_config_path, monkeypatch):
        """VIDKNOT_DOUYIN_COOKIE_FILE 应覆盖配置"""
        monkeypatch.setenv("VIDKNOT_DOUYIN_COOKIE_FILE", "/path/to/cookie.txt")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("douyin", "cookie_file") == "/path/to/cookie.txt"

    def test_env_override_tikhub_api_key(self, tmp_config_path, monkeypatch):
        """TIKHUB_API_KEY 应覆盖配置"""
        monkeypatch.setenv("TIKHUB_API_KEY", "tikhub-test-key")
        c = ConfigManager(config_path=str(tmp_config_path))
        assert c.get("douyin", "tikhub", "api_key") == "tikhub-test-key"


# ===== Pytest Fixtures =====

@pytest.fixture
def tmp_config_path(tmp_path):
    """提供不存在的临时配置文件路径（避免读取项目级 config.yaml）"""
    return tmp_path / "config.yaml"
