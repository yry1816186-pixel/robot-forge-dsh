import ast
from pathlib import Path

import robotd.main as main_module

PACKAGE = Path(main_module.__file__).resolve().parent
NETWORK_MODULES = {"socket", "requests", "urllib", "httpx", "aiohttp", "http"}


def test_no_network_imports_by_default():
    offenders = []
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in NETWORK_MODULES:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in NETWORK_MODULES:
                    offenders.append(f"{path.name}: from {node.module}")
    assert offenders == []


def test_network_defaults_off(monkeypatch):
    monkeypatch.delenv("ROBOTD_NETWORK", raising=False)
    assert main_module.os.environ.get("ROBOTD_NETWORK", "0") == "0"


def test_mic_is_explicitly_enabled(monkeypatch, capsys):
    from robotd.main import run
    from robotd.serial_link import MockLink

    link = MockLink([(0.0, "READY")])
    assert run(link, seconds=0) == 0
    assert "MIC ON" in link.sent
    capsys.readouterr()
