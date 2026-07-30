import re
from pathlib import Path

from vidknot import __version__
from vidknot.adapters.mcp_server import MCPServer
from vidknot.api import app


def test_version_metadata_is_consistent():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', content, re.MULTILINE)

    assert match is not None
    assert __version__ == match.group(1)
    assert app.version == __version__
    assert MCPServer()._handle_initialize({}, 1)["result"]["serverInfo"]["version"] == __version__
