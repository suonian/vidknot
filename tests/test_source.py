"""Tests for the subscription source schema and loaders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vidknot.core.source import (
    SourceConfig,
    SourceKind,
    SourcesFile,
    load_sources_file,
    validate_source,
)
from vidknot.core.source.schema import SourceValidationError


def test_minimal_entry():
    s = validate_source({"name": "x", "platform": "youtube"})
    assert s.name == "x"
    assert s.platform == "youtube"
    assert s.kind is SourceKind.VIDEO_URL
    assert s.url is None
    assert s.tags == ()


def test_full_entry():
    s = validate_source({
        "name": "kol1",
        "platform": "douyin",
        "kind": "channel",
        "url": "https://www.douyin.com/user/EXAMPLE",
        "tags": ["ai", "agents"],
        "schedule": "0 9 * * 1",
        "extra": {"limit": 10},
    })
    assert s.kind is SourceKind.CHANNEL
    assert s.tags == ("ai", "agents")
    assert s.schedule == "0 9 * * 1"
    assert s.extra == {"limit": 10}


def test_missing_name_rejected():
    with pytest.raises(SourceValidationError):
        validate_source({"platform": "youtube"})


def test_missing_platform_rejected():
    with pytest.raises(SourceValidationError):
        validate_source({"name": "x"})


def test_invalid_kind_rejected():
    with pytest.raises(SourceValidationError):
        validate_source({"name": "x", "platform": "yt", "kind": "weird"})


def test_invalid_url_scheme_rejected():
    with pytest.raises(SourceValidationError):
        validate_source({"name": "x", "platform": "yt", "url": "ftp://example.com"})


def test_tags_string_normalized():
    s = validate_source({"name": "x", "platform": "yt", "tags": "a, b , c"})
    assert s.tags == ("a", "b", "c")


@pytest.mark.parametrize(
    "leak",
    [
        "sessionid=abc123def456ghi789",
        "ttwid=abcdef0123456789abcdef",
        "odin_ttid=12345abcd",
        "fpk1=deadbeefcafe",
        "web_session=xyz",
        "AI_PASS=secret_value_here",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.longtokenhere",
        "sk-mp1234567890abcdef1234567890abcdef",
    ],
)
def test_credentials_rejected(leak: str):
    with pytest.raises(SourceValidationError):
        validate_source({
            "name": "x",
            "platform": "yt",
            "url": leak,  # type: ignore[arg-type]
        })
    with pytest.raises(SourceValidationError):
        validate_source({
            "name": leak,  # type: ignore[arg-type]
            "platform": "yt",
        })


def test_load_yaml(tmp_path: Path):
    p = tmp_path / "sources.yaml"
    p.write_text(
        "sources:\n"
        "  - name: a\n"
        "    platform: youtube\n"
        "    url: https://example.com/a\n"
        "  - name: b\n"
        "    platform: douyin\n"
        "    kind: channel\n"
    )
    loaded = load_sources_file(p)
    assert len(loaded.sources) == 2
    assert loaded.sources[0].name == "a"
    assert loaded.sources[1].kind is SourceKind.CHANNEL
    assert loaded.path == p


def test_load_json(tmp_path: Path):
    p = tmp_path / "sources.json"
    p.write_text(json.dumps({"sources": [{"name": "j", "platform": "yt"}]}))
    loaded = load_sources_file(p)
    assert loaded.sources[0].name == "j"


def test_load_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_sources_file(tmp_path / "nope.yaml")


def test_load_rejects_credential(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "sources:\n"
        "  - name: leaked\n"
        "    platform: douyin\n"
        "    url: 'https://x.com?sessionid=DEADBEEFCAFEBABE12345'\n"
    )
    with pytest.raises(SourceValidationError):
        load_sources_file(p)


def test_by_platform():
    s1 = SourceConfig(name="a", platform="youtube")
    s2 = SourceConfig(name="b", platform="douyin")
    s3 = SourceConfig(name="c", platform="youtube")
    bundle = SourcesFile(sources=(s1, s2, s3))
    yt = bundle.by_platform("youtube")
    assert [s.name for s in yt] == ["a", "c"]
