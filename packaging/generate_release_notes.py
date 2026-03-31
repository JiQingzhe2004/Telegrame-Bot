from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CONVENTIONAL_PREFIX_RE = re.compile(
    r"^(feat|fix|chore|docs|refactor|style|test|build|ci|perf|revert)(\([^)]*\))?:\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CommitEntry:
    short_sha: str
    subject: str
    cleaned_subject: str


@dataclass(frozen=True)
class ReleaseStats:
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0

    @property
    def has_content(self) -> bool:
        return any((self.files_changed, self.insertions, self.deletions))


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


def empty_tree() -> str:
    return git("hash-object", "-t", "tree", "/dev/null")


def revision_range(previous_tag: str | None, current_tag: str) -> str:
    return f"{previous_tag}..{current_tag}" if previous_tag else f"{empty_tree()}..{current_tag}"


def clean_subject(subject: str) -> str:
    cleaned = CONVENTIONAL_PREFIX_RE.sub("", subject.strip())
    return cleaned or subject.strip()


def commit_entries(compare_range: str) -> list[CommitEntry]:
    output = git("log", "--no-merges", "--pretty=format:%h%x09%s", compare_range)
    entries: list[CommitEntry] = []
    for line in output.splitlines():
        raw = line.strip()
        if not raw:
            continue
        short_sha, subject = raw.split("\t", 1)
        entries.append(CommitEntry(short_sha=short_sha, subject=subject, cleaned_subject=clean_subject(subject)))
    return entries


def parse_diff_stats(compare_range: str) -> ReleaseStats:
    output = try_git("diff", "--shortstat", compare_range)
    if not output:
        return ReleaseStats()

    files_match = re.search(r"(\d+)\s+files?\s+changed", output)
    insertions_match = re.search(r"(\d+)\s+insertions?\(\+\)", output)
    deletions_match = re.search(r"(\d+)\s+deletions?\(-\)", output)
    return ReleaseStats(
        files_changed=int(files_match.group(1)) if files_match else 0,
        insertions=int(insertions_match.group(1)) if insertions_match else 0,
        deletions=int(deletions_match.group(1)) if deletions_match else 0,
    )


def compare_url(previous_tag: str | None, current_tag: str) -> str | None:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo or not previous_tag:
        return None
    return f"https://github.com/{repo}/compare/{previous_tag}...{current_tag}"


def image_refs(current_tag: str) -> tuple[str, str] | tuple[None, None]:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip().lower()
    if not repo:
        return None, None
    return f"ghcr.io/{repo}:{current_tag}", f"ghcr.io/{repo}:latest"


def category_for(commit: CommitEntry) -> str:
    text = f"{commit.subject} {commit.cleaned_subject}".lower()
    cleaned = commit.cleaned_subject.lower()

    if any(token in cleaned for token in ("修复", "兼容", "补齐", "回退", "修正", "纠正")):
        return "修复优化"
    if any(token in text for token in ("release", "workflow", "docker", "镜像", "打包", "发布", "流水线", "附件", "产物", "tag")):
        return "发布交付"
    if any(token in cleaned for token in ("文档", "说明", "readme", "docs")):
        return "文档说明"
    if any(token in cleaned for token in ("新增", "支持", "实现", "增加", "接入", "重构", "完善", "引入", "自动生成", "自动发现")):
        return "重点更新"
    return "其他变更"


def group_commits(commits: list[CommitEntry]) -> dict[str, list[CommitEntry]]:
    groups = {
        "重点更新": [],
        "修复优化": [],
        "发布交付": [],
        "文档说明": [],
        "其他变更": [],
    }
    for commit in commits:
        groups[category_for(commit)].append(commit)
    return groups


def headline(groups: dict[str, list[CommitEntry]]) -> str:
    parts: list[str] = []
    for label in ("重点更新", "修复优化", "发布交付", "文档说明"):
        count = len(groups[label])
        if count:
            parts.append(f"{count} 项{label}")
    if not parts:
        return "本次版本主要为常规维护更新。"
    if len(parts) == 1:
        return f"本次版本主要包含{parts[0]}。"
    return f"本次版本主要包含{'、'.join(parts)}。"


def highlight_items(groups: dict[str, list[CommitEntry]]) -> list[str]:
    items: list[str] = []
    for label in ("重点更新", "修复优化", "发布交付", "文档说明", "其他变更"):
        for commit in groups[label]:
            items.append(commit.cleaned_subject)
            if len(items) >= 4:
                return items
    return items


def render_diff_stats(stats: ReleaseStats) -> list[str]:
    if not stats.has_content:
        return []
    lines = []
    if stats.files_changed:
        lines.append(f"- 变更文件：{stats.files_changed}")
    if stats.insertions:
        lines.append(f"- 新增行数：{stats.insertions}")
    if stats.deletions:
        lines.append(f"- 删除行数：{stats.deletions}")
    return lines


def render_group_sections(groups: dict[str, list[CommitEntry]]) -> list[str]:
    lines: list[str] = []
    for label in ("重点更新", "修复优化", "发布交付", "文档说明", "其他变更"):
        commits = groups[label]
        if not commits:
            continue
        lines.extend(["", f"## {label}"])
        lines.extend(f"- {commit.cleaned_subject}" for commit in commits)
    return lines


def render_assets(current_tag: str) -> list[str]:
    versioned_image, latest_image = image_refs(current_tag)
    lines = [
        "",
        "## 发布附件",
        "- 源码包：`telegram-moderator-bot-source-bundle.zip`",
        "- Windows：`telegram-moderator-bot-windows-x64.zip`",
        "- Linux：`telegram-moderator-bot-linux-x64.tar.gz`",
        "- macOS：`telegram-moderator-bot-macos-universal.tar.gz`",
    ]
    if versioned_image and latest_image:
        lines.append(f"- Docker 版本标签：`{versioned_image}`")
        lines.append(f"- Docker 最新标签：`{latest_image}`")
    return lines


def render_upgrade_tips() -> list[str]:
    return [
        "",
        "## 升级方式",
        "- Docker / Docker Compose 用户：执行 `docker compose pull && docker compose up -d` 获取最新镜像并重启容器。",
        "- 桌面压缩包用户：请重新下载当前版本附件并覆盖程序文件，保留原有数据目录。",
        "- 源码部署用户：切到当前版本代码后重新安装依赖，并重新构建前端产物。",
    ]


def render_commit_table(commits: list[CommitEntry]) -> list[str]:
    lines = [
        "",
        "## 完整提交记录",
        "| 提交 | 说明 |",
        "| --- | --- |",
    ]
    if not commits:
        lines.append("| - | 无可展示的非合并提交 |")
        return lines

    for commit in commits:
        subject = commit.cleaned_subject.replace("|", r"\|")
        lines.append(f"| `{commit.short_sha}` | {subject} |")
    return lines


def render_release_notes(current_tag: str) -> str:
    previous_tag = previous_tag_for(current_tag)
    compare_range = revision_range(previous_tag, current_tag)
    commits = commit_entries(compare_range)
    groups = group_commits(commits)
    highlights = highlight_items(groups)
    stats = parse_diff_stats(compare_range)
    compare = compare_url(previous_tag, current_tag)
    release_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Telegram 管理机器人 {current_tag}",
        "",
        f"> {headline(groups)}",
        "",
        "## 版本概览",
        f"- 发布时间：{release_date}",
        f"- 当前版本：`{current_tag}`",
        f"- 对比版本：`{previous_tag}`" if previous_tag else "- 对比版本：首个版本发布",
        f"- 提交数量：{len(commits)}",
    ]
    lines.extend(render_diff_stats(stats))
    if compare:
        lines.append(f"- 对比链接：[{previous_tag}...{current_tag}]({compare})")

    lines.extend(["", "## 本次重点"])
    if highlights:
        lines.extend(f"- {item}" for item in highlights)
    else:
        lines.append("- 本次版本没有可展示的非合并提交。")

    lines.extend(render_group_sections(groups))
    lines.extend(render_assets(current_tag))
    lines.extend(render_upgrade_tips())
    lines.extend(render_commit_table(commits))
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
