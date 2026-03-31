from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def try_git(*args: str) -> str | None:
    try:
        return git(*args)
    except subprocess.CalledProcessError:
        return None


def previous_tag_for(current_tag: str) -> str | None:
    return try_git("describe", "--tags", "--abbrev=0", f"{current_tag}^")


def commit_subjects(revision_range: str) -> list[str]:
    output = git("log", "--no-merges", "--pretty=format:%s", revision_range)
    return [line.strip() for line in output.splitlines() if line.strip()]


def compare_url(previous_tag: str | None, current_tag: str) -> str | None:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo or not previous_tag:
        return None
    return f"https://github.com/{repo}/compare/{previous_tag}...{current_tag}"


def render_release_notes(current_tag: str) -> str:
    previous_tag = previous_tag_for(current_tag)
    revision_range = f"{previous_tag}..{current_tag}" if previous_tag else current_tag
    commits = commit_subjects(revision_range)

    lines = [
        f"# {current_tag}",
        "",
        "## 更新范围",
        f"- 当前版本：`{current_tag}`",
        f"- 对比版本：`{previous_tag}`" if previous_tag else "- 对比版本：首个版本发布",
        f"- 提交数量：{len(commits)}",
    ]

    url = compare_url(previous_tag, current_tag)
    if url:
        lines.append(f"- 对比链接：[{previous_tag}...{current_tag}]({url})")

    lines.extend(["", "## 提交摘要"])
    if commits:
        lines.extend(f"- {subject}" for subject in commits)
    else:
        lines.append("- 无可展示的非合并提交")

    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python packaging/generate_release_notes.py <current_tag> [output_path]", file=sys.stderr)
        return 1

    current_tag = sys.argv[1].strip()
    if not current_tag:
        print("current_tag is required", file=sys.stderr)
        return 1

    content = render_release_notes(current_tag)
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
