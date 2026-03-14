from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from bachbot.integrations.pymusica import (
    PyMusicaUnavailableError,
    configured_pymusica_src,
    pymusica_backend_status,
    resolved_pymusica_src,
)


def test_resolved_pymusica_src_uses_sibling_checkout_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACHBOT_PYMUSICA_SRC", raising=False)

    resolved = resolved_pymusica_src()

    assert resolved is not None
    assert resolved.joinpath("pymusica_lang").exists()


def test_resolved_pymusica_src_requires_explicit_env_path_to_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_pymusica_import_state(monkeypatch)
    missing = tmp_path / "missing-src"
    monkeypatch.setenv("BACHBOT_PYMUSICA_SRC", str(missing))

    assert configured_pymusica_src() == missing
    with pytest.raises(PyMusicaUnavailableError, match="BACHBOT_PYMUSICA_SRC"):
        resolved_pymusica_src()

    status = pymusica_backend_status()
    assert status.discovery == "configured-src"
    assert status.available is False
    assert status.import_target == str(missing)
    assert "does not exist" in status.message


def test_pymusica_backend_status_prefers_configured_src(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_pymusica_import_state(monkeypatch)
    src = tmp_path / "src"
    package = src / "pymusica_lang"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "PyMusica"\nrequires-python = ">=3.12"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("BACHBOT_PYMUSICA_SRC", str(src))

    assert resolved_pymusica_src() == src

    status = pymusica_backend_status()
    assert status.discovery == "configured-src"
    assert status.available is True
    assert status.import_target == str(src)
    assert status.requires_python == ">=3.12"
    assert status.runtime_supported is (sys.version_info[:2] >= (3, 12))


def test_pymusica_backend_status_reports_python_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACHBOT_PYMUSICA_SRC", raising=False)

    status = pymusica_backend_status()

    assert status.discovery in {"installed", "sibling-src"}
    assert status.requires_python == ">=3.12"
    assert status.runtime_supported is (sys.version_info[:2] >= (3, 12))
    if not status.runtime_supported:
        assert "Python 3.12+" in status.message


def _clear_pymusica_import_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "pymusica_lang", raising=False)
    cleaned = [entry for entry in sys.path if "/PyMusica/src" not in entry]
    monkeypatch.setattr(sys, "path", cleaned)
    importlib.invalidate_caches()
