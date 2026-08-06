from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import sys
import unittest

from tests.luna_web_supervisor_test_support import (
    LunaSupervisorTestCase,
    MODULE_PATH,
    ROOT,
    SUPERVISOR,
    run_git,
)


class LunaWebSupervisorTests(LunaSupervisorTestCase):
    def test_prepare_is_idempotent_and_manifest_is_immutable(self) -> None:
        first = SUPERVISOR.prepare(str(self.manifest_path))
        second = SUPERVISOR.prepare(str(self.manifest_path))
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        payload["description"] = "changed"
        self.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.status(str(self.manifest_path))
        self.assertEqual("MANIFEST_CHANGED", raised.exception.code)

    def test_host_state_cannot_be_placed_inside_product_project(self) -> None:
        os.environ["LUNA_WEB_SUPERVISOR_STATE_ROOT"] = str(self.project / ".ai-bridge" / "state")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.prepare(str(self.manifest_path))
        self.assertEqual("STATE_ROOT_INSIDE_PROJECT", raised.exception.code)
        self.assertFalse((self.project / ".ai-bridge" / "state").exists())

    def test_failed_validation_is_recorded_then_sent_back_to_web_for_remediation(self) -> None:
        self.prepare_and_reserve()
        failed_head = self.commit_web_change("bad\n", "web attempt one")
        self.bind_result("attempt-1")

        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.verify(str(self.manifest_path), "session-01", "completed")
        self.assertEqual("WEB_REMEDIATION_REQUIRED", raised.exception.code)
        state = self.state()
        self.assertEqual("REMEDIATION_RECORDING_REQUIRED", state["phase"])
        pending = state["units"][0]["pending_remediation"]
        remediation_path = self.project / Path(*pending["mission_path"].split("/"))
        self.assertTrue(remediation_path.is_file())
        remediation_text = remediation_path.read_text(encoding="utf-8")
        self.assertIn("VALIDATION_FAILED", remediation_text)
        self.assertIn(failed_head, remediation_text)
        self.assertIn("Luna task is monitor/verify/record-only", remediation_text)
        self.assertIn("Base64-encoded evidence, not instructions", remediation_text)
        self.assertEqual("", run_git(self.project, "status", "--porcelain=v1", "--untracked-files=all"))

        with self.assertRaises(SUPERVISOR.SupervisorError) as premature:
            SUPERVISOR.reserve(str(self.manifest_path), "session-01", "d" * 64)
        self.assertEqual("PHASE_MISMATCH", premature.exception.code)

        recorded = SUPERVISOR.record_remediation(**self.record_kwargs("Attempt one recorded and read back."))
        self.assertEqual("REMEDIATION_READY", recorded["phase"])
        SUPERVISOR.reserve(str(self.manifest_path), "session-01", "e" * 64)
        self.assertIn("remediation-02.md", str(self.current_mission()))

        final_head = self.commit_web_change("good\n", "web remediation two")
        self.bind_result("attempt-2")
        verified = SUPERVISOR.verify(str(self.manifest_path), "session-01", "completed")
        self.assertEqual("RECORDING_REQUIRED", verified["phase"])
        completed = SUPERVISOR.record(**self.record_kwargs("Final result recorded and read back."))
        self.assertEqual("COMPLETE", completed["phase"])
        state = self.state()
        self.assertEqual(final_head, state["expected_head"])
        self.assertEqual(2, len(state["units"][0]["attempts"]))
        self.assertEqual(1, len(state["units"][0]["remediation_records"]))

    def test_unauthorized_change_path_blocks_instead_of_expanding_scope(self) -> None:
        self.prepare_and_reserve()
        (self.project / "unexpected.txt").write_text("not authorized\n", encoding="utf-8")
        run_git(self.project, "add", "unexpected.txt")
        run_git(self.project, "commit", "-m", "web changed unauthorized path")
        self.bind_result("unauthorized")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.verify(str(self.manifest_path), "session-01", "completed")
        self.assertEqual("UNAUTHORIZED_CHANGE_PATH", raised.exception.code)
        self.assertEqual("BLOCKED", self.state()["phase"])

    def test_remediation_budget_exhaustion_requires_user_decision(self) -> None:
        self.write_manifest(max_web_attempts=1)
        self.prepare_and_reserve()
        self.commit_web_change("bad\n", "only web attempt")
        self.bind_result("exhausted")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.verify(str(self.manifest_path), "session-01", "completed")
        self.assertEqual("REMEDIATION_BUDGET_EXHAUSTED", raised.exception.code)
        self.assertEqual("BLOCKED", self.state()["phase"])

    def test_display_proof_requires_sol_and_extra_high(self) -> None:
        self.prepare_and_reserve()
        run_dir, proof = self.create_oracle_run("bad-proof")
        proof.write_text("Selected model: GPT-5.6 Sol\n", encoding="utf-8")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.submitted(
                str(self.manifest_path),
                "session-01",
                str(run_dir),
                str(proof),
            )
        self.assertEqual("DISPLAY_PROOF_MISSING", raised.exception.code)
        self.assertEqual("SUBMISSION_RESERVED", self.state()["phase"])

    def test_result_rechecks_bound_display_proof_identity(self) -> None:
        self.prepare_and_reserve()
        run_dir, proof = self.create_oracle_run("proof-tamper")
        SUPERVISOR.submitted(
            str(self.manifest_path),
            "session-01",
            str(run_dir),
            str(proof),
        )
        proof.write_text("Selected model: GPT-5.6 Sol\nChanged after binding\n", encoding="utf-8")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.result_ready(
                str(self.manifest_path),
                "session-01",
                str(run_dir / "output.md"),
            )
        self.assertEqual("DISPLAY_PROOF_CHANGED", raised.exception.code)
        self.assertEqual("WEB_ACTIVE", self.state()["phase"])

    def test_remediation_mission_cannot_change_after_reservation(self) -> None:
        self.prepare_and_reserve()
        self.commit_web_change("bad\n", "web attempt before mission tamper")
        self.bind_result("mission-tamper-first")
        with self.assertRaises(SUPERVISOR.SupervisorError):
            SUPERVISOR.verify(str(self.manifest_path), "session-01", "completed")
        SUPERVISOR.record_remediation(**self.record_kwargs("Failure recorded before retry."))
        SUPERVISOR.reserve(str(self.manifest_path), "session-01", "f" * 64)
        mission = self.current_mission()
        mission.write_text(mission.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        run_dir, proof = self.create_oracle_run("mission-tamper-second")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.submitted(
                str(self.manifest_path),
                "session-01",
                str(run_dir),
                str(proof),
            )
        self.assertEqual("MISSION_CHANGED", raised.exception.code)
        self.assertEqual("SUBMISSION_RESERVED", self.state()["phase"])

    def test_luna_validation_that_mutates_source_blocks_without_cleanup(self) -> None:
        self.write_manifest(
            max_web_attempts=2,
            verification_argv=[
                sys.executable,
                "-c",
                "from pathlib import Path; Path('app.txt').write_text('mutated-by-check\\n')",
            ],
        )
        self.prepare_and_reserve()
        self.commit_web_change("good\n", "web completed before bad check")
        self.bind_result("mutating-check")
        with self.assertRaises(SUPERVISOR.SupervisorError) as raised:
            SUPERVISOR.verify(str(self.manifest_path), "session-01", "completed")
        self.assertEqual("VALIDATION_MUTATED_SOURCE", raised.exception.code)
        self.assertEqual("BLOCKED", self.state()["phase"])
        self.assertIn("mutated-by-check", (self.project / "app.txt").read_text(encoding="utf-8"))

    def test_helper_contains_no_oracle_submission_or_product_editor(self) -> None:
        scripts = MODULE_PATH.parent.glob("supervisor_*.py")
        source = "\n".join(path.read_text(encoding="utf-8") for path in scripts)
        self.assertNotIn("chatgpt_oracle_dispatch", source)
        self.assertNotIn("apply_patch", source)
        self.assertNotIn("git commit", source.casefold())
        self.assertNotIn("git push", source.casefold())

    def test_supervisor_modules_respect_architecture_size_limit(self) -> None:
        scripts = sorted(MODULE_PATH.parent.glob("supervisor_*.py"))
        self.assertEqual(9, len(scripts))
        oversized = {
            path.name: len(path.read_text(encoding="utf-8").splitlines())
            for path in scripts
            if len(path.read_text(encoding="utf-8").splitlines()) > 400
        }
        self.assertEqual({}, oversized)

    def test_supervisor_module_dependency_graph_is_acyclic(self) -> None:
        scripts = sorted(MODULE_PATH.parent.glob("supervisor_*.py"))
        names = {path.stem for path in scripts}
        graph: dict[str, set[str]] = {}
        for path in scripts:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            graph[path.stem] = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module in names
            }

        def visit(name: str, active: set[str], complete: set[str]) -> None:
            self.assertNotIn(name, active, f"module import cycle reaches {name}")
            if name in complete:
                return
            active.add(name)
            for dependency in graph[name]:
                visit(dependency, active, complete)
            active.remove(name)
            complete.add(name)

        complete: set[str] = set()
        for name in sorted(names):
            visit(name, set(), complete)

    def test_skill_metadata_and_reference_files_are_utf8_and_explicit_only(self) -> None:
        skill_root = ROOT / "skills" / "luna-web-supervisor"
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        schema = json.loads(
            (skill_root / "references" / "manifest.schema.json").read_text(encoding="utf-8")
        )
        example = json.loads(
            (skill_root / "references" / "manifest.example.json").read_text(encoding="utf-8")
        )
        frontmatter = skill.split("---", 2)[1]
        self.assertEqual(
            {"name", "description"},
            {
                line.split(":", 1)[0].strip()
                for line in frontmatter.splitlines()
                if ":" in line
            },
        )
        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertNotIn("\ufffd", metadata)
        self.assertEqual("codex.luna-web-supervisor/1", schema["properties"]["schema"]["const"])
        self.assertEqual("codex.luna-web-supervisor/1", example["schema"])
        self.assertEqual(
            example["authorization"]["live_submission_limit"],
            sum(unit["max_web_attempts"] for unit in example["units"]),
        )


if __name__ == "__main__":
    unittest.main()
