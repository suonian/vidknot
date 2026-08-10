"""Regression tests for credential loading and provider isolation.

Origin: Hermes (Shanghai) agent contributed these tests to prevent secret
contamination from generic OPENAI_* env vars leaking into an isolated
ConfigManager instance. Adapted for v0.3.3 where LLM_API_KEY intentionally
maps to BOTH openai and openai-compatible (backward compatibility).

Run with: pytest tests/test_env_secrets.py -v
"""
from __future__ import annotations

from pathlib import Path

from vidknot.utils.config_manager import ConfigManager


def _write_minimal_config(config_path: Path, provider_block: str) -> None:
    """Write a minimal config.yaml with the given provider block text."""
    config_path.write_text(
        "providers:\n"
        f"{provider_block}\n"
    )


def test_llm_api_key_maps_to_both_openai_and_openai_compatible(
    monkeypatch, tmp_path
) -> None:
    """LLM_API_KEY populates both openai and openai-compatible providers.

    v0.3.3 keeps the dual mapping for backward compatibility with users who
    set LLM_API_KEY before openai-compatible was introduced. If the user
    prefers strict isolation, they should set providers.<name>.api_key
    directly in config.yaml.
    """
    config = tmp_path / "config.yaml"
    _write_minimal_config(
        config,
        "  default_provider: openai-compatible\n"
        "  openai:\n"
        "    api_key: ''\n"
        "    base_url: https://example.invalid/v1\n"
        "    model: test-model\n"
        "  openai-compatible:\n"
        "    api_key: ''\n"
        "    base_url: https://example.invalid/v1\n"
        "    model: test-model\n",
    )
    monkeypatch.setenv("LLM_API_KEY", "shared-llm-secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(ConfigManager, "_dotenv", {}, raising=False)

    manager = ConfigManager(config_path=str(config))

    # Both providers receive the shared key
    assert (
        manager.get("providers", "openai-compatible", "api_key")
        == "shared-llm-secret"
    )
    assert manager.get("providers", "openai", "api_key") == "shared-llm-secret"


def test_openai_api_key_only_read_from_process_env(
    monkeypatch, tmp_path
) -> None:
    """OPENAI_API_KEY is NEVER loaded from .env (process-only).

    Rationale: OPENAI_API_KEY in a shared .env (e.g. ~/.hermes/.env) may
    belong to a different agent (the host). Reading it from .env would
    silently inject the wrong credentials into vidknot's openai provider.
    """
    config = tmp_path / "config.yaml"
    _write_minimal_config(config, "  openai:\n    api_key: ''\n")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        ConfigManager,
        "_dotenv",
        {"OPENAI_API_KEY": "should-not-be-loaded"},
        raising=False,
    )

    manager = ConfigManager(config_path=str(config))
    assert manager.get("providers", "openai", "api_key") in (None, "")


def test_explicit_process_env_overrides_dotenv(
    monkeypatch, tmp_path
) -> None:
    """When a variable exists in BOTH process env and .env, process env wins."""
    config = tmp_path / "config.yaml"
    _write_minimal_config(config, "  siliconflow:\n    api_key: ''\n")

    monkeypatch.setenv("SILICONFLOW_API_KEY", "explicit-process-value")
    monkeypatch.setattr(
        ConfigManager,
        "_dotenv",
        {"SILICONFLOW_API_KEY": "dotenv-value-should-lose"},
        raising=False,
    )

    manager = ConfigManager(config_path=str(config))
    assert (
        manager.get("providers", "siliconflow", "api_key")
        == "explicit-process-value"
    )


def test_openai_model_does_not_contaminate_isolated_config_manager(
    monkeypatch, tmp_path
) -> None:
    """An explicit config_path= instance must NOT pick up OPENAI_MODEL.

    When the caller passes config_path=..., they're signaling that they
    want full isolation (e.g. embedder, test fixture). The generic
    OPENAI_MODEL env var used by the host agent must not leak in.
    """
    config = tmp_path / "isolated-config.yaml"
    _write_minimal_config(config, "  openai:\n    model: gpt-4o-mini\n")

    monkeypatch.setenv("OPENAI_MODEL", "host-model-should-not-leak")

    # Construct with an isolated config_path that does NOT match the
    # default config discovery path.
    manager = ConfigManager(config_path=str(config))
    assert (
        manager.get("providers", "openai", "model") == "gpt-4o-mini"
    )


def test_openai_model_applies_when_using_default_config_path(
    monkeypatch, tmp_path
) -> None:
    """OPENAI_MODEL DOES apply when using the default config discovery path.

    This is the convenience behavior for normal CLI usage.
    """
    # Place a config in cwd that ConfigManager._find_config_path() will pick up.
    cwd_config = Path.cwd() / "config.yaml"
    original_content = cwd_config.read_text() if cwd_config.exists() else None

    try:
        # Append a test section instead of overwriting real config.yaml
        with cwd_config.open("a", encoding="utf-8") as f:
            f.write(
                "\n# test_openai_model_applies\n"
                "providers:\n"
                "  openai:\n"
                "    model: should-be-overridden-by-env\n"
            )
        monkeypatch.setenv("OPENAI_MODEL", "env-model-wins")
        manager = ConfigManager()  # no config_path -> uses default
        assert (
            manager.get("providers", "openai", "model")
            == "env-model-wins"
        )
    finally:
        # Restore original config.yaml content
        if original_content is None:
            cwd_config.unlink(missing_ok=True)
        else:
            cwd_config.write_text(original_content, encoding="utf-8")
