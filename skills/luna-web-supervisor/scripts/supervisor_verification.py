from __future__ import annotations

"""Verify Web GPT outcomes and route bounded failures back to Web GPT."""

from pathlib import Path
import subprocess
from typing import Any

from supervisor_core import (
    REMEDIABLE_CODES,
    SupervisorError,
    exclusive_lock,
    iso_now,
    read_json,
    resolve_project_path,
    sha256_file,
    write_atomic,
)
from supervisor_git import (
    ensure_forward_history,
    git_changed_paths,
    git_identity,
    git_status,
    require_clean,
    run_git,
)
from supervisor_records import block_state
from supervisor_remediation import create_remediation_packet, verification_log_path
from supervisor_store import (
    current_attempt,
    load_existing,
    public_status,
    require_phase,
    save_state,
)


def verify(manifest_path: str, unit_id: str, outcome_name_value: str) -> dict[str, object]:
    manifest, _, state_dir = load_existing(manifest_path)
    outcome_name = outcome_name_value.strip().casefold()
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        unit_state = require_phase(state, "RESULT_READY", unit_id)
        unit_manifest = manifest["units"][state["current_unit_index"]]
        outcomes = {outcome["name"]: outcome for outcome in unit_manifest["outcomes"]}
        if outcome_name not in outcomes:
            raise SupervisorError(
                "OUTCOME_NOT_AUTHORIZED",
                "web result outcome is not authorized for this unit",
                {"outcome": outcome_name, "authorized": sorted(outcomes)},
            )
        outcome = outcomes[outcome_name]
        root = Path(manifest["project_root"])
        attempt = current_attempt(unit_state)
        try:
            require_clean(root, "WEB_RESULT_DIRTY")
            _, end_head = git_identity(root)
            start_head = attempt["start_head"]
            policy = outcome["commit_policy"]
            if end_head != start_head:
                ensure_forward_history(root, start_head, end_head)
            attempt_paths = git_changed_paths(root, start_head, end_head) if end_head != start_head else []
            expected_paths = outcome["expected_change_paths"]
            authorized_paths = sorted(
                {
                    path
                    for authorized_outcome in unit_manifest["outcomes"]
                    for path in authorized_outcome["expected_change_paths"]
                }
            )
            unauthorized_attempt_paths = sorted(set(attempt_paths) - set(authorized_paths))
            if unauthorized_attempt_paths:
                raise SupervisorError(
                    "UNAUTHORIZED_CHANGE_PATH",
                    "the web attempt committed a path outside every authorized outcome",
                    {"authorized": authorized_paths, "actual": attempt_paths, "extra": unauthorized_attempt_paths},
                )
            if attempt["kind"] == "remediation":
                if end_head == start_head:
                    raise SupervisorError("LOCAL_COMMIT_MISSING", "web remediation requires a new local commit")
            else:
                if policy == "required" and end_head == start_head:
                    raise SupervisorError("LOCAL_COMMIT_MISSING", "completed web work requires a local commit")
                if policy == "forbidden" and end_head != start_head:
                    raise SupervisorError(
                        "OUTCOME_REQUIRES_REVERSION",
                        "this outcome must restore the unit to no net product diff",
                        {"attempt_paths": attempt_paths},
                    )
                if policy == "optional" and end_head == start_head and expected_paths:
                    raise SupervisorError("EXPECTED_CHANGE_MISSING", "optional commit omitted declared expected changes")

            initial_head = unit_state["initial_head"]
            cumulative_paths = (
                git_changed_paths(root, initial_head, end_head) if end_head != initial_head else []
            )
            cumulative_extra = sorted(set(cumulative_paths) - set(expected_paths))
            cumulative_missing = sorted(set(expected_paths) - set(cumulative_paths))
            if cumulative_extra:
                if set(cumulative_extra) - set(authorized_paths):
                    raise SupervisorError(
                        "UNAUTHORIZED_CHANGE_PATH",
                        "the unit has a net change outside every authorized outcome",
                        {
                            "expected": expected_paths,
                            "actual": cumulative_paths,
                            "extra": cumulative_extra,
                        },
                    )
                raise SupervisorError(
                    "OUTCOME_REQUIRES_REVERSION",
                    "the selected outcome still has authorized paths that must be reverted",
                    {"expected": expected_paths, "actual": cumulative_paths, "extra": cumulative_extra},
                )
            if cumulative_missing:
                raise SupervisorError(
                    "EXPECTED_CHANGE_MISSING",
                    "the selected outcome is missing an exact authorized product change",
                    {"expected": expected_paths, "actual": cumulative_paths, "missing": cumulative_missing},
                )
            check_results: list[dict[str, Any]] = []
            for index, command in enumerate(outcome["verification_commands"]):
                cwd = root if command["cwd"] == "." else resolve_project_path(
                    root, command["cwd"], must_exist=True
                )
                before_head = run_git(root, ["rev-parse", "HEAD"]).stdout.strip().casefold()
                require_clean(root, "VALIDATION_PRECONDITION_DIRTY")
                started = iso_now()
                timed_out = False
                try:
                    process = subprocess.run(
                        command["argv"],
                        cwd=str(cwd),
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        timeout=command["timeout_seconds"],
                        shell=False,
                    )
                    exit_code = process.returncode
                    stdout = process.stdout
                    stderr = process.stderr
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    exit_code = None
                    stdout = exc.stdout if isinstance(exc.stdout, str) else ""
                    stderr = exc.stderr if isinstance(exc.stderr, str) else ""
                log = {
                    "schema": "codex.luna-web-supervisor-verification/1",
                    "unit_id": unit_id,
                    "name": command["name"],
                    "argv": command["argv"],
                    "cwd": str(cwd),
                    "started_at": started,
                    "finished_at": iso_now(),
                    "timeout_seconds": command["timeout_seconds"],
                    "timed_out": timed_out,
                    "expected_exit_code": command["expected_exit_code"],
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                }
                log_path = verification_log_path(
                    state_dir,
                    unit_id,
                    attempt["number"],
                    index,
                    command["name"],
                )
                write_atomic(log_path, log)
                current_head = run_git(root, ["rev-parse", "HEAD"]).stdout.strip().casefold()
                dirty = git_status(root)
                if current_head != before_head or dirty:
                    raise SupervisorError(
                        "VALIDATION_MUTATED_SOURCE",
                        "a Luna validation command changed tracked or untracked project state",
                        {
                            "command": command["name"],
                            "head_before": before_head,
                            "head_after": current_head,
                            "status": dirty[-5000:],
                            "log": str(log_path),
                        },
                    )
                passed = not timed_out and exit_code == command["expected_exit_code"]
                check_results.append(
                    {
                        "name": command["name"],
                        "passed": passed,
                        "exit_code": exit_code,
                        "log_path": str(log_path),
                        "log_sha256": sha256_file(log_path),
                    }
                )
                if not passed:
                    raise SupervisorError(
                        "VALIDATION_FAILED",
                        "a declared validation command did not pass",
                        check_results[-1],
                    )
            unit_state["status"] = "VERIFIED"
            unit_state["end_head"] = end_head
            attempt["status"] = "VERIFIED"
            attempt["end_head"] = end_head
            unit_state["verification"] = {
                "outcome": outcome_name,
                "commit_policy": policy,
                "attempt_number": attempt["number"],
                "attempt_changed_paths": attempt_paths,
                "changed_paths": cumulative_paths,
                "checks": check_results,
                "verified_at": iso_now(),
            }
            state["phase"] = "RECORDING_REQUIRED"
            save_state(
                state_dir,
                state,
                "VERIFIED",
                {
                    "outcome": outcome_name,
                    "attempt_number": attempt["number"],
                    "end_head": end_head,
                    "changed_paths": cumulative_paths,
                },
            )
            return public_status(state_dir, state)
        except SupervisorError as exc:
            attempt["status"] = "VERIFICATION_FAILED"
            attempt["verification_failure"] = {
                "code": exc.code,
                "message": str(exc),
                "evidence": exc.evidence,
                "at": iso_now(),
            }
            try:
                _, observed_head = git_identity(root)
            except SupervisorError:
                observed_head = attempt["start_head"]
            attempt["end_head"] = observed_head
            has_budget = len(unit_state["attempts"]) < unit_state["max_web_attempts"]
            can_remediate = exc.code in REMEDIABLE_CODES and has_budget and not git_status(root)
            if can_remediate:
                packet = create_remediation_packet(
                    manifest,
                    unit_manifest,
                    unit_state,
                    attempt,
                    exc,
                    observed_head,
                )
                unit_state["status"] = "REMEDIATION_RECORDING_REQUIRED"
                unit_state["pending_remediation"] = packet
                state["expected_head"] = observed_head
                state["phase"] = "REMEDIATION_RECORDING_REQUIRED"
                save_state(
                    state_dir,
                    state,
                    "WEB_REMEDIATION_REQUIRED",
                    {
                        "failure_code": exc.code,
                        "source_attempt": attempt["number"],
                        "next_attempt": packet["next_attempt"],
                        "mission_path": packet["mission_path"],
                        "mission_sha256": packet["mission_sha256"],
                    },
                )
                raise SupervisorError(
                    "WEB_REMEDIATION_REQUIRED",
                    "record this failure, then send the frozen remediation mission back to Web GPT",
                    {
                        "original_failure": exc.envelope()["error"],
                        "remediation": packet,
                        "remaining_attempts": unit_state["max_web_attempts"] - len(unit_state["attempts"]),
                    },
                ) from exc
            if exc.code in REMEDIABLE_CODES and not has_budget:
                exhausted = SupervisorError(
                    "REMEDIATION_BUDGET_EXHAUSTED",
                    "web remediation attempts are exhausted; user decision is required",
                    {
                        "original_failure": exc.envelope()["error"],
                        "max_web_attempts": unit_state["max_web_attempts"],
                    },
                )
                block_state(state_dir, state, exhausted.code, str(exhausted), exhausted.evidence)
                raise exhausted from exc
            block_state(state_dir, state, exc.code, str(exc), exc.evidence)
            raise
