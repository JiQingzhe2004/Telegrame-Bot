from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepare_runtime() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
        os.chdir(base_dir)
        return

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    os.chdir(repo_root)


def main() -> None:
    _prepare_runtime()
    from bot.main import main as bot_main

    bot_main()


if __name__ == "__main__":
    main()
