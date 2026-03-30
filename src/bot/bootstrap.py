from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"[init] running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    web_admin = root / "web-admin"

    # 1) 安装后端依赖（当前 Python 环境）
    _run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], root)

    # 2) 安装前端依赖
    npm = shutil.which("npm")
    if not npm:
        print("[init] warning: npm 未安装，已跳过前端依赖安装（web-admin）。")
        print("[init] 如需前端，请先安装 Node.js，再执行：npm --prefix web-admin install")
        return

    if not web_admin.exists():
        print("[init] warning: 未找到 web-admin 目录，跳过前端依赖安装。")
        return

    _run([npm, "--prefix", "web-admin", "install"], root)
    _run([npm, "--prefix", "web-admin", "run", "build"], root)
    print("[init] 完成：后端与前端依赖已安装，前端已构建。")


if __name__ == "__main__":
    main()
