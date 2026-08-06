from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "skills"
    / "luna-web-supervisor"
    / "scripts"
    / "supervisor_state.py"
)
SPEC = importlib.util.spec_from_file_location("luna_web_supervisor_state_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
SUPERVISOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUPERVISOR
SPEC.loader.exec_module(SUPERVISOR)


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class LunaSupervisorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        run_git(self.project, "init")
        run_git(self.project, "config", "user.name", "Web GPT Test")
        run_git(self.project, "config", "user.email", "web-gpt@example.invalid")
        (self.project / ".gitignore").write_text(".ai-bridge/\n", encoding="utf-8")
        (self.project / "app.txt").write_text("initial\n", encoding="utf-8")
        mission = self.project / ".ai-bridge" / "session-01.md"
        mission.parent.mkdir()
        mission.write_text(
            "# Session 01\n\nChange app.txt to the approved value and commit it.\n",
            encoding="utf-8",
        )
        run_git(self.project, "add", ".gitignore", "app.txt")
        run_git(self.project, "commit", "-m", "test baseline")
        self.manifest_path = self.project / ".ai-bridge" / "supervisor.json"
        self.record_url = "https://app.notion.com/p/exact-test-record"
        self.state_root = self.root / "host-state"
        self.previous_state_root = os.environ.get("LUNA_WEB_SUPERVISOR_STATE_ROOT")
        os.environ["LUNA_WEB_SUPERVISOR_STATE_ROOT"] = str(self.state_root)
        self.addCleanup(self.restore_state_root)
        self.write_manifest(max_web_attempts=2)

    def restore_state_root(self) -> None:
        if self.previous_state_root is None:
            os.environ.pop("LUNA_WEB_SUPERVISOR_STATE_ROOT", None)
        else:
            os.environ["LUNA_WEB_SUPERVISOR_STATE_ROOT"] = self.previous_state_root

    def write_manifest(
        self,
        *,
        max_web_attempts: int,
        verification_argv: list[str] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        argv = verification_argv or [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "assert Path('app.txt').read_text(encoding='utf-8') == 'good\\n'"
            ),
        ]
        payload = {
            "schema": "codex.luna-web-supervisor/1",
            "supervisor_id": "test-supervisor",
            "description": "Unit-test supervisor batch.",
            "project_root": str(self.project.resolve()),
            "role": "monitor-record-only",
            "supervisor": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "high",
                "source_writes": False,
            },
            "web": {
                "transport": "oracle-devspace",
                "mode": "orchestrator",
                "model": "GPT-5.6 Sol",
                "dispatcher_reasoning_level": "Very High",
                "visible_reasoning": "Extra High",
                "concurrency": 1,
            },
            "authorization": {
                "request_fingerprint": "a" * 64,
                "authorized_at": now.isoformat(),
                "expires_at": (now + timedelta(days=1)).isoformat(),
                "exact_unit_ids": ["session-01"],
                "live_submission_limit": max_web_attempts,
                "local_commit": True,
                "push": False,
                "deploy": False,
            },
            "recording": {
                "notion_required": True,
                "project_checkpoint_dir": ".ai-bridge/luna-web-supervisor",
                "targets": [
                    {
                        "kind": "notion",
                        "url": self.record_url,
                        "purpose": "Store and read back every unit checkpoint.",
                    }
                ],
            },
            "context_refs": [],
            "units": [
                {
                    "id": "session-01",
                    "description": "Test one serialized unit.",
                    "mission_path": ".ai-bridge/session-01.md",
                    "max_web_attempts": max_web_attempts,
                    "context_refs": [],
                    "outcomes": [
                        {
                            "name": "completed",
                            "commit_policy": "required",
                            "expected_change_paths": ["app.txt"],
                            "verification_commands": [
                                {
                                    "name": "app-contract",
                                    "argv": argv,
                                    "cwd": ".",
                                    "timeout_seconds": 30,
                                    "expected_exit_code": 0,
                                }
                            ],
                        },
                        {
                            "name": "hold",
                            "commit_policy": "forbidden",
                            "expected_change_paths": [],
                            "verification_commands": [],
                        },
                        {
                            "name": "choice_issue",
                            "commit_policy": "forbidden",
                            "expected_change_paths": [],
                            "verification_commands": [],
                        },
                    ],
                }
            ],
        }
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def prepare_and_reserve(self, preview: str = "b" * 64) -> dict[str, object]:
        prepared = SUPERVISOR.prepare(str(self.manifest_path))
        self.assertEqual("UNIT_READY", prepared["phase"])
        return SUPERVISOR.reserve(
            str(self.manifest_path),
            "session-01",
            preview,
        )

    def state(self) -> dict[str, object]:
        status = SUPERVISOR.status(str(self.manifest_path))
        return json.loads((Path(status["state_dir"]) / "state.json").read_text(encoding="utf-8"))

    def current_mission(self) -> Path:
        state = self.state()
        attempt = state["units"][0]["attempts"][-1]
        return self.project / Path(*attempt["mission_path"].split("/"))

    def create_oracle_run(self, label: str) -> tuple[Path, Path]:
        state = self.state()
        attempt = state["units"][0]["attempts"][-1]
        mission = self.project / Path(*attempt["mission_path"].split("/"))
        run_dir = self.root / f"oracle-{label}"
        run_dir.mkdir()
        oracle_state = {
            "schema": "codex.chatgpt.oracle-state/v1",
            "project_root": str(self.project.resolve()),
            "mode": "orchestrator",
            "transport": "devspace",
            "profile": {
                "model": "gpt-5.6",
                "model_strategy": "select",
                "thinking_time": "heavy",
            },
            "mission": {
                "path": str(mission.resolve()),
                "sha256": SUPERVISOR.sha256_file(mission),
            },
            "oracle": {
                "slug": f"test-{label}",
            },
            "status": "complete",
            "exit_code": 0,
        }
        (run_dir / "state.json").write_text(
            json.dumps(oracle_state),
            encoding="utf-8",
        )
        proof = run_dir / "stdout.log"
        proof.write_text(
            "Selected model: GPT-5.6 Sol\nVisible reasoning: Extra High\n",
            encoding="utf-8",
        )
        output = run_dir / "output.md"
        output.write_text(f"Web result for {label}\n", encoding="utf-8")
        return run_dir, proof

    def bind_result(self, label: str) -> None:
        run_dir, proof = self.create_oracle_run(label)
        SUPERVISOR.submitted(
            str(self.manifest_path),
            "session-01",
            str(run_dir),
            str(proof),
        )
        SUPERVISOR.result_ready(
            str(self.manifest_path),
            "session-01",
            str(run_dir / "output.md"),
        )

    def commit_web_change(self, value: str, message: str) -> str:
        (self.project / "app.txt").write_text(value, encoding="utf-8")
        run_git(self.project, "add", "app.txt")
        run_git(self.project, "commit", "-m", message)
        return run_git(self.project, "rev-parse", "HEAD")

    def record_kwargs(self, summary: str) -> dict[str, object]:
        return {
            "manifest_path": str(self.manifest_path),
            "unit_id": "session-01",
            "record_refs": [self.record_url],
            "readback_fingerprint_value": "c" * 64,
            "summary": summary,
        }
