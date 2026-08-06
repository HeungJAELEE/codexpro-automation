from __future__ import annotations

"""Notion/readback gates and terminal blocking for Luna supervision."""

from pathlib import Path
from typing import Any

from supervisor_core import (
    HEX64,
    SupervisorError,
    exclusive_lock,
    iso_now,
    nonempty_text,
    normalize_url,
    read_json,
    safe_id,
)
from supervisor_store import (
    current_unit,
    load_existing,
    public_status,
    require_phase,
    save_state,
)


def block_state(
    state_dir: Path,
    state: dict[str, Any],
    code: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    unit = current_unit(state)
    if unit is not None:
        unit["status"] = "BLOCKED"
    state["phase"] = "BLOCKED"
    state["block"] = {
        "code": code,
        "message": message,
        "evidence": evidence or {},
        "at": iso_now(),
    }
    save_state(state_dir, state, "BLOCKED", state["block"])


def normalize_record_evidence(
    manifest: dict[str, Any],
    record_refs: list[str],
    readback_fingerprint_value: str,
    summary: str,
) -> tuple[list[str], str, str]:
    fingerprint = readback_fingerprint_value.casefold()
    if HEX64.fullmatch(fingerprint) is None:
        raise SupervisorError("READBACK_FINGERPRINT_INVALID", "readback fingerprint must be SHA-256")
    normalized_summary = nonempty_text(summary, "summary", maximum=1000)
    expected_refs = sorted(target["url"] for target in manifest["recording"]["targets"])
    actual_refs = sorted({normalize_url(value, "record_ref") for value in record_refs})
    if actual_refs != expected_refs:
        raise SupervisorError(
            "RECORD_TARGET_MISMATCH",
            "record refs must exactly match the frozen recording targets",
            {"expected": expected_refs, "actual": actual_refs},
        )
    return actual_refs, fingerprint, normalized_summary


def record_remediation(
    manifest_path: str,
    unit_id: str,
    record_refs: list[str],
    readback_fingerprint_value: str,
    summary: str,
) -> dict[str, object]:
    manifest, _, state_dir = load_existing(manifest_path)
    actual_refs, fingerprint, normalized_summary = normalize_record_evidence(
        manifest,
        record_refs,
        readback_fingerprint_value,
        summary,
    )
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        unit = require_phase(state, "REMEDIATION_RECORDING_REQUIRED", unit_id)
        pending = unit.get("pending_remediation")
        if not isinstance(pending, dict):
            raise SupervisorError("STATE_INVALID", "no pending remediation packet exists")
        remediation_record = {
            "source_attempt": pending["source_attempt"],
            "next_attempt": pending["next_attempt"],
            "mission_path": pending["mission_path"],
            "mission_sha256": pending["mission_sha256"],
            "refs": actual_refs,
            "readback_fingerprint": fingerprint,
            "summary": normalized_summary,
            "recorded_at": iso_now(),
        }
        unit["remediation_records"].append(remediation_record)
        unit["status"] = "REMEDIATION_READY"
        state["phase"] = "REMEDIATION_READY"
        save_state(
            state_dir,
            state,
            "REMEDIATION_RECORDED",
            {
                "source_attempt": pending["source_attempt"],
                "next_attempt": pending["next_attempt"],
                "record_refs": actual_refs,
                "readback_fingerprint": fingerprint,
            },
        )
        return public_status(state_dir, state)


def record(
    manifest_path: str,
    unit_id: str,
    record_refs: list[str],
    readback_fingerprint_value: str,
    summary: str,
) -> dict[str, object]:
    manifest, _, state_dir = load_existing(manifest_path)
    actual_refs, fingerprint, normalized_summary = normalize_record_evidence(
        manifest,
        record_refs,
        readback_fingerprint_value,
        summary,
    )
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        unit = require_phase(state, "RECORDING_REQUIRED", unit_id)
        unit["record"] = {
            "refs": actual_refs,
            "readback_fingerprint": fingerprint,
            "summary": normalized_summary,
            "recorded_at": iso_now(),
        }
        unit["status"] = "COMPLETE"
        state["expected_head"] = unit["end_head"] or state["expected_head"]
        state["current_unit_index"] += 1
        state["block"] = None
        state["phase"] = "COMPLETE" if state["current_unit_index"] >= len(state["units"]) else "UNIT_READY"
        save_state(
            state_dir,
            state,
            "UNIT_RECORDED",
            {"record_refs": actual_refs, "readback_fingerprint": fingerprint},
        )
        return public_status(state_dir, state)


def block(
    manifest_path: str,
    unit_id: str,
    code: str,
    message: str,
    evidence_refs: list[str],
) -> dict[str, object]:
    _, _, state_dir = load_existing(manifest_path)
    normalized_code = safe_id(code, "code").upper().replace("-", "_").replace(".", "_")
    normalized_message = nonempty_text(message, "message", maximum=2000)
    with exclusive_lock(state_dir):
        state = read_json(state_dir / "state.json")
        if state["phase"] in {"COMPLETE", "BLOCKED"}:
            raise SupervisorError("PHASE_MISMATCH", "completed or blocked state cannot be blocked again")
        require_phase(state, state["phase"], unit_id)
        block_state(
            state_dir,
            state,
            normalized_code,
            normalized_message,
            {"refs": [nonempty_text(item, "evidence_ref", maximum=1000) for item in evidence_refs]},
        )
        return public_status(state_dir, state)
