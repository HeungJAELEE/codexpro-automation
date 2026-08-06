from __future__ import annotations

"""Durable state persistence for serialized Luna-supervised work units."""

import os
from pathlib import Path
from typing import Any

from supervisor_core import (
    PHASES,
    ROLE,
    STATE_SCHEMA,
    SupervisorError,
    append_event,
    canonical_bytes,
    exclusive_lock,
    iso_now,
    parse_datetime,
    read_json,
    resolve_project_path,
    sha256_bytes,
    sha256_file,
    utc_now,
    write_atomic,
    write_bytes_atomic,
)
from supervisor_git import git_identity, git_path_is_ignored, require_clean
from supervisor_manifest import normalize_manifest


def state_root() -> Path:
    override = os.environ.get("LUNA_WEB_SUPERVISOR_STATE_ROOT")
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise SupervisorError(
                "STATE_ROOT_INVALID",
                "LUNA_WEB_SUPERVISOR_STATE_ROOT must be absolute",
            )
        return root.resolve(strict=False)
    return (Path.home() / ".codex" / "state" / "luna-web-supervisor").resolve(strict=False)


def state_dir_for(manifest: dict[str, Any]) -> Path:
    root = state_root()
    project_root = Path(manifest["project_root"])
    try:
        root.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise SupervisorError(
            "STATE_ROOT_INSIDE_PROJECT",
            "host-only supervisor state must remain outside the exact project root",
            {"state_root": str(root), "project_root": str(project_root)},
        )
    project_key = sha256_bytes(manifest["project_root"].casefold().encode("utf-8"))[:20]
    return root / "projects" / project_key / manifest["supervisor_id"]


def event(state: dict[str, Any], kind: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    state["event_sequence"] += 1
    return {
        "schema": "codex.luna-web-supervisor-event/1",
        "sequence": state["event_sequence"],
        "at": iso_now(),
        "kind": kind,
        "phase": state["phase"],
        "unit_id": current_unit_id(state),
        "details": details or {},
    }


def save_state(state_dir: Path, state: dict[str, Any], kind: str, details: dict[str, Any] | None = None) -> None:
    state["updated_at"] = iso_now()
    next_event = event(state, kind, details)
    write_atomic(state_dir / "state.json", state)
    append_event(state_dir / "events.jsonl", next_event)


def current_unit(state: dict[str, Any]) -> dict[str, Any] | None:
    index = state["current_unit_index"]
    if index >= len(state["units"]):
        return None
    return state["units"][index]


def current_unit_id(state: dict[str, Any]) -> str | None:
    unit = current_unit(state)
    return unit["id"] if unit else None


def current_attempt(unit: dict[str, Any]) -> dict[str, Any]:
    attempts = unit.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise SupervisorError("ATTEMPT_MISSING", "current unit has no reserved web attempt")
    return attempts[-1]


def next_action(phase: str) -> str:
    return {
        "UNIT_READY": "dry_run_preview_then_reserve_exact_unit",
        "REMEDIATION_READY": "dry_run_preview_then_reserve_exact_web_remediation",
        "SUBMISSION_RESERVED": "submit_exact_unit_once_or_block_without_resubmission",
        "WEB_ACTIVE": "wait_for_or_recover_only_the_exact_oracle_run",
        "RESULT_READY": "verify_declared_outcome_without_local_repair",
        "REMEDIATION_RECORDING_REQUIRED": "record_failure_readback_then_return_to_web",
        "RECORDING_REQUIRED": "write_and_read_back_exact_record_targets",
        "BLOCKED": "user_decision_required_no_local_repair",
        "COMPLETE": "batch_complete",
    }[phase]


def public_status(state_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "schema": STATE_SCHEMA,
        "supervisor_id": state["supervisor_id"],
        "phase": state["phase"],
        "current_unit_id": current_unit_id(state),
        "completed_units": sum(unit["status"] == "COMPLETE" for unit in state["units"]),
        "total_units": len(state["units"]),
        "live_submission_reservations": state["live_submission_reservations"],
        "live_submission_limit": state["live_submission_limit"],
        "expected_head": state["expected_head"],
        "next_action": next_action(state["phase"]),
        "state_dir": str(state_dir),
        "block": state.get("block"),
    }


def check_frozen_missions(manifest: dict[str, Any], state: dict[str, Any]) -> None:
    root = Path(manifest["project_root"])
    expected = {unit["id"]: unit for unit in state["units"]}
    for unit in manifest["units"]:
        path = resolve_project_path(root, unit["mission_path"], must_exist=True)
        actual = sha256_file(path)
        frozen = expected[unit["id"]]["mission_sha256"]
        if actual != frozen:
            raise SupervisorError(
                "MISSION_CHANGED",
                "a frozen unit mission changed after preparation",
                {"unit_id": unit["id"], "expected_sha256": frozen, "actual_sha256": actual},
            )


def load_manifest(path_value: str) -> tuple[Path, dict[str, Any], bytes, Path]:
    path = Path(path_value).expanduser().resolve(strict=True)
    manifest = normalize_manifest(read_json(path), path)
    frozen = canonical_bytes(manifest)
    return path, manifest, frozen, state_dir_for(manifest)


def load_existing(path_value: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    _, manifest, frozen, state_dir = load_manifest(path_value)
    snapshot_path = state_dir / "manifest.json"
    state_path = state_dir / "state.json"
    if not snapshot_path.is_file() or not state_path.is_file():
        raise SupervisorError(
            "SUPERVISOR_NOT_PREPARED",
            "prepare this exact manifest before continuing",
            {"state_dir": str(state_dir)},
        )
    snapshot = snapshot_path.read_bytes()
    if snapshot != frozen:
        raise SupervisorError(
            "MANIFEST_CHANGED",
            "the prepared supervisor manifest is immutable",
            {
                "prepared_sha256": sha256_bytes(snapshot),
                "current_sha256": sha256_bytes(frozen),
            },
        )
    state = read_json(state_path)
    if state.get("schema") != STATE_SCHEMA or state.get("manifest_sha256") != sha256_bytes(snapshot):
        raise SupervisorError("STATE_INVALID", "supervisor state is corrupt or belongs to another manifest")
    if state.get("phase") not in PHASES:
        raise SupervisorError("STATE_INVALID", "supervisor phase is invalid")
    check_frozen_missions(manifest, state)
    return manifest, state, state_dir


def require_phase(state: dict[str, Any], expected: str, unit_id: str | None = None) -> dict[str, Any]:
    if state["phase"] != expected:
        raise SupervisorError(
            "PHASE_MISMATCH",
            "supervisor command is not valid in the current phase",
            {"expected": expected, "actual": state["phase"], "unit_id": current_unit_id(state)},
        )
    unit = current_unit(state)
    if unit is None:
        raise SupervisorError("NO_CURRENT_UNIT", "the supervisor has no current unit")
    if unit_id is not None and unit["id"] != unit_id:
        raise SupervisorError(
            "UNIT_ORDER_MISMATCH",
            "only the exact next unit may advance",
            {"expected": unit["id"], "actual": unit_id},
        )
    return unit


def prepare(manifest_path: str) -> dict[str, Any]:
    _, manifest, frozen, state_dir = load_manifest(manifest_path)
    with exclusive_lock(state_dir):
        snapshot_path = state_dir / "manifest.json"
        state_path = state_dir / "state.json"
        if snapshot_path.exists() or state_path.exists():
            if not snapshot_path.is_file() or not state_path.is_file() or snapshot_path.read_bytes() != frozen:
                raise SupervisorError("MANIFEST_CHANGED", "existing supervisor state belongs to different bytes")
            state = read_json(state_path)
            check_frozen_missions(manifest, state)
            return {**public_status(state_dir, state), "idempotent": True}
        expires_at = parse_datetime(manifest["authorization"]["expires_at"], "authorization.expires_at")
        if expires_at <= utc_now():
            raise SupervisorError("AUTHORIZATION_EXPIRED", "batch authorization already expired")
        root = Path(manifest["project_root"])
        _, head = git_identity(root)
        require_clean(root, "PREPARE_REQUIRES_CLEAN_WORKTREE")
        checkpoint_dir = manifest["recording"]["project_checkpoint_dir"]
        checkpoint_probe = f"{checkpoint_dir.rstrip('/')}/.ignore-probe"
        if not git_path_is_ignored(root, checkpoint_probe):
            raise SupervisorError(
                "CHECKPOINT_DIR_NOT_IGNORED",
                "the Luna checkpoint directory must be ignored by Git",
                {"project_checkpoint_dir": checkpoint_dir},
            )
        units = []
        for unit in manifest["units"]:
            mission = resolve_project_path(root, unit["mission_path"], must_exist=True)
            units.append(
                {
                    "id": unit["id"],
                    "status": "PENDING",
                    "mission_path": unit["mission_path"],
                    "mission_sha256": sha256_file(mission),
                    "max_web_attempts": unit["max_web_attempts"],
                    "attempts": [],
                    "initial_head": None,
                    "end_head": None,
                    "verification": None,
                    "record": None,
                    "pending_remediation": None,
                    "remediation_records": [],
                }
            )
        state = {
            "schema": STATE_SCHEMA,
            "supervisor_id": manifest["supervisor_id"],
            "project_root": manifest["project_root"],
            "manifest_sha256": sha256_bytes(frozen),
            "role": ROLE,
            "phase": "UNIT_READY",
            "current_unit_index": 0,
            "expected_head": head,
            "live_submission_reservations": 0,
            "live_submission_limit": manifest["authorization"]["live_submission_limit"],
            "event_sequence": 0,
            "units": units,
            "block": None,
            "created_at": iso_now(),
            "updated_at": iso_now(),
        }
        state_dir.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(snapshot_path, frozen)
        save_state(state_dir, state, "PREPARED", {"head": head, "unit_count": len(units)})
        return {**public_status(state_dir, state), "idempotent": False}


def status(manifest_path: str) -> dict[str, Any]:
    manifest, state, state_dir = load_existing(manifest_path)
    del manifest, state
    with exclusive_lock(state_dir):
        current = read_json(state_dir / "state.json")
        return public_status(state_dir, current)
