from __future__ import annotations

"""Oracle attempt reservation and result-identity transitions."""

from pathlib import Path

from supervisor_core import (
    HEX64,
    MODEL_PROOF,
    REASONING_PROOF,
    SupervisorError,
    exclusive_lock,
    nonempty_text,
    parse_datetime,
    read_json,
    resolve_project_path,
    sha256_file,
    utc_now,
)
from supervisor_git import git_identity, require_clean, within
from supervisor_store import (
    current_attempt,
    load_existing,
    public_status,
    require_phase,
    save_state,
)


def reserve(manifest_path: str, unit_id: str, preview_sha256: str) -> dict[str, object]:
    manifest, _, state_dir = load_existing(manifest_path)
    preview = preview_sha256.casefold()
    if HEX64.fullmatch(preview) is None:
        raise SupervisorError("PREVIEW_HASH_INVALID", "preview_sha256 must be SHA-256")
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        if state["phase"] not in {"UNIT_READY", "REMEDIATION_READY"}:
            raise SupervisorError(
                "PHASE_MISMATCH",
                "only a ready initial or remediation unit may be reserved",
                {"actual": state["phase"]},
            )
        unit = require_phase(state, state["phase"], unit_id)
        expires_at = parse_datetime(manifest["authorization"]["expires_at"], "authorization.expires_at")
        if expires_at <= utc_now():
            raise SupervisorError("AUTHORIZATION_EXPIRED", "authorization expired before this unit was reserved")
        if state["live_submission_reservations"] >= state["live_submission_limit"]:
            raise SupervisorError("SUBMISSION_LIMIT_REACHED", "no authorized live submission remains")
        if len(unit["attempts"]) >= unit["max_web_attempts"]:
            raise SupervisorError(
                "REMEDIATION_BUDGET_EXHAUSTED",
                "this unit has no authorized web attempt remaining",
                {"max_web_attempts": unit["max_web_attempts"]},
            )
        root = Path(manifest["project_root"])
        _, head = git_identity(root)
        require_clean(root, "RESERVE_REQUIRES_CLEAN_WORKTREE")
        if head != state["expected_head"]:
            raise SupervisorError(
                "START_FINGERPRINT_MISMATCH",
                "the next unit does not start from the recorded commit",
                {"expected": state["expected_head"], "actual": head},
            )
        attempt_number = len(unit["attempts"]) + 1
        if state["phase"] == "UNIT_READY":
            mission_path = unit["mission_path"]
            mission_sha256 = unit["mission_sha256"]
            attempt_kind = "initial"
            if attempt_number != 1:
                raise SupervisorError("STATE_INVALID", "initial unit may only create attempt one")
            unit["initial_head"] = head
        else:
            pending = unit.get("pending_remediation")
            if not isinstance(pending, dict):
                raise SupervisorError("STATE_INVALID", "remediation-ready unit has no remediation packet")
            mission_path = pending["mission_path"]
            mission_file = resolve_project_path(root, mission_path, must_exist=True)
            mission_sha256 = sha256_file(mission_file)
            if mission_sha256 != pending["mission_sha256"]:
                raise SupervisorError("MISSION_CHANGED", "remediation mission changed before reservation")
            attempt_kind = "remediation"
        attempt = {
            "number": attempt_number,
            "kind": attempt_kind,
            "status": "SUBMISSION_RESERVED",
            "mission_path": mission_path,
            "mission_sha256": mission_sha256,
            "start_head": head,
            "end_head": None,
            "preview_sha256": preview,
            "oracle": None,
            "result": None,
            "verification_failure": None,
        }
        unit["attempts"].append(attempt)
        unit["status"] = "SUBMISSION_RESERVED"
        unit["pending_remediation"] = None
        state["live_submission_reservations"] += 1
        state["phase"] = "SUBMISSION_RESERVED"
        save_state(
            state_dir,
            state,
            "SUBMISSION_RESERVED",
            {
                "attempt_number": attempt_number,
                "attempt_kind": attempt_kind,
                "mission_sha256": mission_sha256,
                "preview_sha256": preview,
            },
        )
        return public_status(state_dir, state)


def submitted(
    manifest_path: str,
    unit_id: str,
    run_dir_value: str,
    display_proof_value: str,
) -> dict[str, object]:
    manifest, _, state_dir = load_existing(manifest_path)
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        unit = require_phase(state, "SUBMISSION_RESERVED", unit_id)
        attempt = current_attempt(unit)
        run_dir = Path(run_dir_value).expanduser().resolve(strict=True)
        if not run_dir.is_dir():
            raise SupervisorError("ORACLE_RUN_INVALID", "run_dir must be a directory")
        oracle_state_path = (run_dir / "state.json").resolve(strict=True)
        if not within(run_dir, oracle_state_path):
            raise SupervisorError("ORACLE_RUN_INVALID", "Oracle state path escapes run_dir")
        oracle_state = read_json(oracle_state_path)
        if oracle_state.get("project_root") != manifest["project_root"]:
            raise SupervisorError("ORACLE_PROJECT_MISMATCH", "Oracle run belongs to a different project")
        if oracle_state.get("mode") != "orchestrator" or oracle_state.get("transport") != "devspace":
            raise SupervisorError(
                "ORACLE_ROUTE_MISMATCH",
                "Oracle run must be orchestrator over DevSpace",
                {"mode": oracle_state.get("mode"), "transport": oracle_state.get("transport")},
            )
        mission = oracle_state.get("mission") if isinstance(oracle_state.get("mission"), dict) else {}
        expected_mission = resolve_project_path(
            Path(manifest["project_root"]),
            attempt["mission_path"],
            must_exist=True,
        )
        current_mission_sha256 = sha256_file(expected_mission)
        if current_mission_sha256 != attempt["mission_sha256"]:
            raise SupervisorError(
                "MISSION_CHANGED",
                "the reserved attempt mission changed before Oracle submission was bound",
                {
                    "expected_sha256": attempt["mission_sha256"],
                    "actual_sha256": current_mission_sha256,
                },
            )
        try:
            actual_mission = Path(str(mission.get("path") or "")).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SupervisorError("ORACLE_MISSION_MISMATCH", "Oracle mission path is unavailable") from exc
        if (
            actual_mission != expected_mission
            or str(mission.get("sha256") or "").casefold() != attempt["mission_sha256"]
        ):
            raise SupervisorError(
                "ORACLE_MISSION_MISMATCH",
                "Oracle run did not submit the exact frozen attempt mission",
                {
                    "expected_path": str(expected_mission),
                    "actual_path": str(actual_mission),
                    "expected_sha256": attempt["mission_sha256"],
                    "actual_sha256": mission.get("sha256"),
                },
            )
        profile = oracle_state.get("profile") if isinstance(oracle_state.get("profile"), dict) else {}
        if (
            str(profile.get("model") or "").casefold() != "gpt-5.6"
            or str(profile.get("model_strategy") or "").casefold() != "select"
            or str(profile.get("thinking_time") or "").casefold() != "heavy"
        ):
            raise SupervisorError(
                "ORACLE_PROFILE_MISMATCH",
                "Oracle run did not preserve the configured Sol/heavy selection route",
                {"profile": profile},
            )
        oracle = oracle_state.get("oracle") if isinstance(oracle_state.get("oracle"), dict) else {}
        slug = nonempty_text(oracle.get("slug"), "oracle.slug", maximum=500)
        display_proof = Path(display_proof_value).expanduser().resolve(strict=True)
        if not display_proof.is_file() or not within(run_dir, display_proof):
            raise SupervisorError(
                "DISPLAY_PROOF_INVALID",
                "model/reasoning proof must be one file inside the exact Oracle run",
            )
        try:
            proof_text = display_proof.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise SupervisorError("DISPLAY_PROOF_INVALID", "could not read model/reasoning proof") from exc
        if MODEL_PROOF.search(proof_text) is None or REASONING_PROOF.search(proof_text) is None:
            raise SupervisorError(
                "DISPLAY_PROOF_MISSING",
                "proof does not contain both GPT-5.6 Sol and Extra High",
                {"proof_path": str(display_proof)},
            )
        unit["status"] = "WEB_ACTIVE"
        attempt["status"] = "WEB_ACTIVE"
        attempt["oracle"] = {
            "run_dir": str(run_dir),
            "state_path": str(oracle_state_path),
            "state_sha256": sha256_file(oracle_state_path),
            "slug": slug,
            "display_proof_path": str(display_proof),
            "display_proof_sha256": sha256_file(display_proof),
        }
        state["phase"] = "WEB_ACTIVE"
        save_state(
            state_dir,
            state,
            "WEB_ACTIVE",
            {"attempt_number": attempt["number"], "slug": slug, "run_dir": str(run_dir)},
        )
        return public_status(state_dir, state)


def result_ready(manifest_path: str, unit_id: str, result_path_value: str) -> dict[str, object]:
    manifest, _, state_dir = load_existing(manifest_path)
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        unit = require_phase(state, "WEB_ACTIVE", unit_id)
        attempt = current_attempt(unit)
        run_dir = Path(attempt["oracle"]["run_dir"]).resolve(strict=True)
        oracle_state = read_json(run_dir / "state.json")
        if oracle_state.get("status") != "complete" or oracle_state.get("exit_code") != 0:
            raise SupervisorError(
                "ORACLE_NOT_COMPLETE",
                "only a durable complete Oracle run may enter result verification",
                {
                    "status": oracle_state.get("status"),
                    "exit_code": oracle_state.get("exit_code"),
                    "run_dir": str(run_dir),
                },
            )
        if (
            oracle_state.get("project_root") != manifest["project_root"]
            or oracle_state.get("mode") != "orchestrator"
            or oracle_state.get("transport") != "devspace"
        ):
            raise SupervisorError(
                "ORACLE_ROUTE_MISMATCH",
                "the completed Oracle run no longer matches the bound project and route",
            )
        mission = oracle_state.get("mission") if isinstance(oracle_state.get("mission"), dict) else {}
        expected_mission = resolve_project_path(
            Path(manifest["project_root"]),
            attempt["mission_path"],
            must_exist=True,
        )
        try:
            actual_mission = Path(str(mission.get("path") or "")).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SupervisorError("ORACLE_MISSION_MISMATCH", "Oracle mission path is unavailable") from exc
        current_mission_sha256 = sha256_file(expected_mission)
        if (
            actual_mission != expected_mission
            or current_mission_sha256 != attempt["mission_sha256"]
            or str(mission.get("sha256") or "").casefold() != attempt["mission_sha256"]
        ):
            raise SupervisorError(
                "ORACLE_MISSION_MISMATCH",
                "the completed Oracle run no longer matches the frozen attempt mission",
                {
                    "expected_path": str(expected_mission),
                    "actual_path": str(actual_mission),
                    "expected_sha256": attempt["mission_sha256"],
                    "file_sha256": current_mission_sha256,
                    "oracle_sha256": mission.get("sha256"),
                },
            )
        profile = oracle_state.get("profile") if isinstance(oracle_state.get("profile"), dict) else {}
        if (
            str(profile.get("model") or "").casefold() != "gpt-5.6"
            or str(profile.get("model_strategy") or "").casefold() != "select"
            or str(profile.get("thinking_time") or "").casefold() != "heavy"
        ):
            raise SupervisorError(
                "ORACLE_PROFILE_MISMATCH",
                "the completed Oracle run no longer preserves the configured Sol/heavy selection route",
                {"profile": profile},
            )
        oracle = oracle_state.get("oracle") if isinstance(oracle_state.get("oracle"), dict) else {}
        if oracle.get("slug") != attempt["oracle"]["slug"]:
            raise SupervisorError("ORACLE_SLUG_MISMATCH", "Oracle conversation ownership changed")
        display_proof = Path(attempt["oracle"]["display_proof_path"]).resolve(strict=True)
        if (
            not within(run_dir, display_proof)
            or sha256_file(display_proof) != attempt["oracle"]["display_proof_sha256"]
        ):
            raise SupervisorError(
                "DISPLAY_PROOF_CHANGED",
                "model/reasoning proof changed after the Oracle run was bound",
            )
        result_path = Path(result_path_value).expanduser().resolve(strict=True)
        expected_result = (run_dir / "output.md").resolve(strict=True)
        if result_path != expected_result or not result_path.is_file() or result_path.stat().st_size == 0:
            raise SupervisorError(
                "ORACLE_RESULT_INVALID",
                "result must be the exact fresh nonempty output.md from the recorded Oracle run",
                {"expected": str(expected_result), "actual": str(result_path)},
            )
        unit["status"] = "RESULT_READY"
        attempt["status"] = "RESULT_READY"
        attempt["result"] = {
            "path": str(result_path),
            "sha256": sha256_file(result_path),
            "size_bytes": result_path.stat().st_size,
        }
        state["phase"] = "RESULT_READY"
        save_state(
            state_dir,
            state,
            "RESULT_READY",
            {"attempt_number": attempt["number"], "result_sha256": attempt["result"]["sha256"]},
        )
        return public_status(state_dir, state)
