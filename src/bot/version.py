from __future__ import annotations

import re
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


PACKAGE_NAME = "telegram-moderator-bot"
VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def _read_version_from_pyproject() -> str | None:
    root = Path(__file__).resolve().parents[2]
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    match = VERSION_RE.search(pyproject.read_text(encoding="utf-8"))
    if not match:
        return None
    return match.group(1).strip()


@lru_cache(maxsize=1)
def get_backend_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return _read_version_from_pyproject() or "0.0.0"
