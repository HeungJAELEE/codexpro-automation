from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    path = ROOT / "scripts" / "validate_cloud_first.py"
    spec = importlib.util.spec_from_file_location("cloud_first_validator", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cloud_contract_is_exact_and_pc_independent() -> None:
    contract = json.loads(
        (ROOT / "contracts" / "cloud" / "cloud-first-v1.json").read_text(encoding="utf-8")
    )
    assert contract["default_lane"] == "codex-cloud"
    assert contract["source_of_truth"] == "github"
    assert contract["cloud_lane"]["host_dependency"] == "none"
    assert contract["local_lane"]["status"] == "optional-explicit-only"
    assert contract["dirty_worktree_policy"] == (
        "synchronize-to-explicit-backup-branch-or-block"
    )


def test_cloud_first_validator_accepts_the_repository() -> None:
    validator = load_validator()
    assert validator.validate(ROOT) == []


def test_cloud_job_is_linux_and_has_no_api_secret_dependency() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-portability.yml").read_text(
        encoding="utf-8"
    )
    cloud_job = workflow.split("cloud-first:", 1)[1].split("portable:", 1)[0]
    assert "runs-on: ubuntu-latest" in cloud_job
    assert "scripts/validate_cloud_first.py" in cloud_job
    assert "OPENAI_API_KEY" not in cloud_job
    assert "tailscale" not in cloud_job.casefold()


def test_local_browser_automation_remains_explicit_and_recoverable() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    routing = (ROOT / "docs" / "GLOBAL_CHATGPT_ROUTING.md").read_text(encoding="utf-8")
    assert "explicit local-only lane" in agents
    assert "Oracle + DevSpace" in routing
    assert "exact persisted" in routing
