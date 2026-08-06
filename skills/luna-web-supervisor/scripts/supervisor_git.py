from __future__ import annotations

"""Read-only Git identity and change-boundary helpers."""

from pathlib import Path
import re
import subprocess
from typing import Sequence

from supervisor_core import HEX64, SupervisorError


def run_git(project_root: Path, arguments: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(project_root), *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise SupervisorError(
            "GIT_COMMAND_FAILED",
            "read-only Git command failed",
            {
                "argv": ["git", "-C", str(project_root), *arguments],
                "exit_code": result.returncode,
                "stderr": result.stderr[-2000:],
            },
        )
    return result


def git_identity(project_root: Path) -> tuple[str, str]:
    root = Path(run_git(project_root, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve(strict=True)
    if root != project_root:
        raise SupervisorError(
            "GIT_ROOT_MISMATCH",
            "project_root must be the exact Git root",
            {"project_root": str(project_root), "git_root": str(root)},
        )
    head = run_git(project_root, ["rev-parse", "HEAD"]).stdout.strip().casefold()
    if HEX64.fullmatch(head) is None and re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise SupervisorError("GIT_HEAD_INVALID", "could not resolve a commit fingerprint")
    return str(root), head


def git_status(project_root: Path) -> str:
    return run_git(project_root, ["status", "--porcelain=v1", "--untracked-files=all"]).stdout


def git_path_is_ignored(project_root: Path, relative: str) -> bool:
    result = run_git(
        project_root,
        ["check-ignore", "--quiet", "--no-index", "--", relative],
        check=False,
    )
    return result.returncode == 0


def require_clean(project_root: Path, code: str) -> None:
    status = git_status(project_root)
    if status:
        raise SupervisorError(
            code,
            "the exact project worktree is not clean",
            {"status": status[-5000:]},
        )


def git_changed_paths(project_root: Path, start_head: str, end_head: str) -> list[str]:
    result = run_git(
        project_root,
        ["diff", "--name-only", "--diff-filter=ACDMRTUXB", start_head, end_head],
    )
    return sorted({line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()})


def ensure_forward_history(project_root: Path, start_head: str, end_head: str) -> None:
    ancestor = run_git(project_root, ["merge-base", "--is-ancestor", start_head, end_head], check=False)
    if ancestor.returncode != 0:
        raise SupervisorError(
            "HISTORY_DIVERGED",
            "the Web GPT result is not a forward descendant of the reserved start commit",
            {"start_head": start_head, "end_head": end_head},
        )
    merges = run_git(project_root, ["rev-list", "--merges", f"{start_head}..{end_head}"]).stdout.strip()
    if merges:
        raise SupervisorError(
            "MERGE_COMMIT_UNEXPECTED",
            "continuous supervision does not accept merge commits inside one unit",
            {"merge_commits": merges.splitlines()},
        )


def within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False
