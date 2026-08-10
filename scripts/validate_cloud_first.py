#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


EXPECTED_CONTRACT = {
    "schema": "codexpro.cloud-first/v1",
    "default_lane": "codex-cloud",
    "source_of_truth": "github",
    "task_result": "branch-or-pull-request",
    "cloud_lane": {
        "host_dependency": "none",
        "checkout_source": "github-branch-or-commit",
        "agent_internet": "off-by-default",
        "secrets": "environment-setup-only",
        "required_gates": [
            "repository-agents-loaded",
            "declared-tests-pass",
            "diff-reviewed",
            "remote-branch-pushed",
            "ci-observed",
        ],
    },
    "local_lane": {
        "status": "optional-explicit-only",
        "host_dependency": "awake-and-online",
        "allowed_uses": [
            "unpublished-local-files",
            "signed-in-desktop-apps",
            "exact-persisted-run-recovery",
        ],
    },
    "dirty_worktree_policy": "synchronize-to-explicit-backup-branch-or-block",
    "completion_policy": "remote-evidence-only",
    "bridge_role": "optional-local-adapter",
}


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    contract_path = root / "contracts" / "cloud" / "cloud-first-v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract != EXPECTED_CONTRACT:
        failures.append("cloud contract differs from codexpro.cloud-first/v1")

    manifest = json.loads((root / "install-manifest.json").read_text(encoding="utf-8"))
    expected_routing = {
        "new_work_engine": "codex-cloud",
        "regular_workspace_transport": "github",
        "local_workspace_transport": "oracle-devspace-explicit-only",
        "pro_transport": "codex-cloud-default-or-explicit-oracle-local",
        "agbrowse": "persisted-run-recovery-only",
        "codexpro": "persisted-run-recovery-only",
    }
    if manifest.get("routing") != expected_routing:
        failures.append("install manifest routing is not cloud-first")

    required_text = {
        "AGENTS.md": (
            "GitHub is the source of truth",
            "Codex Cloud is the default execution lane",
            "must not infer unpublished local bytes",
        ),
        "docs/GLOBAL_CHATGPT_ROUTING.md": (
            "Cloud-first default",
            "explicit local-only lane",
            "PC-off acceptance",
        ),
        "docs/CLOUD_FIRST_OPERATIONS.md": (
            "Codex Cloud environment",
            "synchronize-to-explicit-backup-branch-or-block",
            "PC-off acceptance test",
        ),
        "README.md": ("기본 실행 경로는 Codex Cloud", "PC가 꺼져 있어도"),
        "README.en.md": ("default execution lane is Codex Cloud", "when the PC is off"),
    }
    for relative, needles in required_text.items():
        value = (root / relative).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in value:
                failures.append(f"{relative} is missing {needle!r}")

    workflow = (root / ".github" / "workflows" / "release-portability.yml").read_text(
        encoding="utf-8"
    )
    if "cloud-first:" not in workflow or "runs-on: ubuntu-latest" not in workflow:
        failures.append("CI lacks the PC-independent ubuntu cloud-first job")
    if "scripts/validate_cloud_first.py" not in workflow:
        failures.append("CI does not execute the cloud-first validator")

    forbidden = "Every new ChatGPT submission uses Oracle"
    if forbidden in (root / "AGENTS.md").read_text(encoding="utf-8"):
        failures.append("AGENTS.md still declares Oracle as the universal new-work route")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the PC-independent cloud-first contract.")
    parser.add_argument("--root", default=".", help="Repository root to validate.")
    args = parser.parse_args(argv)
    failures = validate(Path(args.root).resolve())
    if failures:
        print("cloud-first validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("cloud-first validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
