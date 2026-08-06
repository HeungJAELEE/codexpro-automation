from __future__ import annotations

"""Validation and normalization for immutable Luna supervision manifests."""

from datetime import timedelta
from pathlib import Path
from typing import Any

from supervisor_core import (
    COMMIT_POLICIES,
    HEX64,
    MANIFEST_SCHEMA,
    OUTCOME_NAMES,
    ROLE,
    SUPERVISOR_CONTRACT,
    WEB_CONTRACT,
    SupervisorError,
    nonempty_text,
    normalize_context_refs,
    normalize_relative,
    parse_datetime,
    require_keys,
    resolve_project_path,
    safe_id,
)


def normalize_verification_commands(
    values: Any,
    field: str,
    project_root: Path,
) -> list[dict[str, Any]]:
    if not isinstance(values, list) or len(values) > 20:
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be an array of at most 20 commands")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, item in enumerate(values):
        item_field = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise SupervisorError("MANIFEST_INVALID", f"{item_field} must be an object")
        require_keys(
            item,
            {"name", "argv", "timeout_seconds", "expected_exit_code"},
            {"cwd"},
            item_field,
        )
        name = safe_id(item["name"], f"{item_field}.name")
        if name in names:
            raise SupervisorError("MANIFEST_INVALID", f"{field} contains duplicate command names", {"name": name})
        names.add(name)
        argv = item["argv"]
        if not isinstance(argv, list) or not argv or len(argv) > 64:
            raise SupervisorError("MANIFEST_INVALID", f"{item_field}.argv must be a nonempty string array")
        normalized_argv = [
            nonempty_text(argument, f"{item_field}.argv[{argument_index}]", maximum=2000)
            for argument_index, argument in enumerate(argv)
        ]
        timeout = item["timeout_seconds"]
        exit_code = item["expected_exit_code"]
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 3600:
            raise SupervisorError("MANIFEST_INVALID", f"{item_field}.timeout_seconds must be 1..3600")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool) or not -255 <= exit_code <= 255:
            raise SupervisorError("MANIFEST_INVALID", f"{item_field}.expected_exit_code must be an integer")
        cwd = normalize_relative(item.get("cwd", "."), f"{item_field}.cwd") if item.get("cwd", ".") != "." else "."
        if cwd != ".":
            directory = resolve_project_path(project_root, cwd, must_exist=True)
            if not directory.is_dir():
                raise SupervisorError("MANIFEST_INVALID", f"{item_field}.cwd must resolve to a directory")
        result.append(
            {
                "name": name,
                "argv": normalized_argv,
                "cwd": cwd,
                "timeout_seconds": timeout,
                "expected_exit_code": exit_code,
            }
        )
    return result


def normalize_manifest(payload: dict[str, Any], source_path: Path) -> dict[str, Any]:
    require_keys(
        payload,
        {
            "schema",
            "supervisor_id",
            "project_root",
            "role",
            "supervisor",
            "web",
            "authorization",
            "recording",
            "units",
        },
        {"context_refs", "description"},
        "manifest",
    )
    if payload["schema"] != MANIFEST_SCHEMA:
        raise SupervisorError("MANIFEST_SCHEMA_UNSUPPORTED", "unsupported supervisor manifest schema")
    supervisor_id = safe_id(payload["supervisor_id"], "supervisor_id")
    project_root_value = nonempty_text(payload["project_root"], "project_root", maximum=1000)
    project_root = Path(project_root_value).expanduser()
    if not project_root.is_absolute():
        raise SupervisorError("MANIFEST_INVALID", "project_root must be absolute")
    try:
        project_root = project_root.resolve(strict=True)
    except OSError as exc:
        raise SupervisorError("PROJECT_ROOT_UNAVAILABLE", "project_root does not exist") from exc
    if not project_root.is_dir():
        raise SupervisorError("PROJECT_ROOT_UNAVAILABLE", "project_root must be a directory")
    if payload["role"] != ROLE:
        raise SupervisorError("ROLE_INVALID", f"role must be {ROLE}")

    supervisor = payload["supervisor"]
    if not isinstance(supervisor, dict):
        raise SupervisorError("MANIFEST_INVALID", "supervisor must be an object")
    require_keys(supervisor, set(SUPERVISOR_CONTRACT), set(), "supervisor")
    normalized_supervisor = {
        "model": nonempty_text(supervisor["model"], "supervisor.model", maximum=100),
        "reasoning_effort": nonempty_text(
            supervisor["reasoning_effort"], "supervisor.reasoning_effort", maximum=30
        ).casefold(),
        "source_writes": supervisor["source_writes"],
    }
    if normalized_supervisor != SUPERVISOR_CONTRACT:
        raise SupervisorError(
            "SUPERVISOR_CONTRACT_INVALID",
            "Luna must be fixed to high effort with product source writes disabled",
            {"required": SUPERVISOR_CONTRACT, "actual": normalized_supervisor},
        )

    web = payload["web"]
    if not isinstance(web, dict):
        raise SupervisorError("MANIFEST_INVALID", "web must be an object")
    require_keys(web, set(WEB_CONTRACT), set(), "web")
    normalized_web = {
        "transport": nonempty_text(web["transport"], "web.transport", maximum=50).casefold(),
        "mode": nonempty_text(web["mode"], "web.mode", maximum=50).casefold(),
        "model": nonempty_text(web["model"], "web.model", maximum=100),
        "dispatcher_reasoning_level": nonempty_text(
            web["dispatcher_reasoning_level"], "web.dispatcher_reasoning_level", maximum=50
        ),
        "visible_reasoning": nonempty_text(web["visible_reasoning"], "web.visible_reasoning", maximum=50),
        "concurrency": web["concurrency"],
    }
    if normalized_web != WEB_CONTRACT:
        raise SupervisorError(
            "WEB_CONTRACT_INVALID",
            "Web GPT must use the serialized Oracle DevSpace Sol Extra High contract",
            {"required": WEB_CONTRACT, "actual": normalized_web},
        )

    authorization = payload["authorization"]
    if not isinstance(authorization, dict):
        raise SupervisorError("MANIFEST_INVALID", "authorization must be an object")
    require_keys(
        authorization,
        {
            "request_fingerprint",
            "authorized_at",
            "expires_at",
            "exact_unit_ids",
            "live_submission_limit",
            "local_commit",
            "push",
            "deploy",
        },
        set(),
        "authorization",
    )
    request_fingerprint = nonempty_text(
        authorization["request_fingerprint"], "authorization.request_fingerprint", maximum=64
    ).casefold()
    if HEX64.fullmatch(request_fingerprint) is None:
        raise SupervisorError("MANIFEST_INVALID", "authorization.request_fingerprint must be SHA-256")
    authorized_at = parse_datetime(authorization["authorized_at"], "authorization.authorized_at")
    expires_at = parse_datetime(authorization["expires_at"], "authorization.expires_at")
    if expires_at <= authorized_at or expires_at - authorized_at > timedelta(days=30):
        raise SupervisorError(
            "MANIFEST_INVALID",
            "authorization must expire after authorization and within 30 days",
        )
    for flag in ("local_commit", "push", "deploy"):
        if not isinstance(authorization[flag], bool):
            raise SupervisorError("MANIFEST_INVALID", f"authorization.{flag} must be boolean")
    if authorization["push"] or authorization["deploy"]:
        raise SupervisorError(
            "EXTERNAL_EFFECT_FORBIDDEN",
            "this supervisor never authorizes push or deploy",
        )

    units = payload["units"]
    if not isinstance(units, list) or not 1 <= len(units) <= 100:
        raise SupervisorError("MANIFEST_INVALID", "units must contain 1..100 exact work units")
    normalized_units: list[dict[str, Any]] = []
    unit_ids: list[str] = []
    for unit_index, unit in enumerate(units):
        unit_field = f"units[{unit_index}]"
        if not isinstance(unit, dict):
            raise SupervisorError("MANIFEST_INVALID", f"{unit_field} must be an object")
        require_keys(
            unit,
            {"id", "mission_path", "outcomes", "max_web_attempts"},
            {"context_refs", "description"},
            unit_field,
        )
        unit_id = safe_id(unit["id"], f"{unit_field}.id")
        if unit_id in unit_ids:
            raise SupervisorError("MANIFEST_INVALID", "unit ids must be unique", {"unit_id": unit_id})
        unit_ids.append(unit_id)
        max_web_attempts = unit["max_web_attempts"]
        if (
            not isinstance(max_web_attempts, int)
            or isinstance(max_web_attempts, bool)
            or not 1 <= max_web_attempts <= 10
        ):
            raise SupervisorError(
                "MANIFEST_INVALID",
                f"{unit_field}.max_web_attempts must be 1..10",
            )
        mission_relative = normalize_relative(unit["mission_path"], f"{unit_field}.mission_path")
        mission_path = resolve_project_path(project_root, mission_relative, must_exist=True)
        if not mission_path.is_file() or mission_path.stat().st_size == 0:
            raise SupervisorError(
                "MISSION_INVALID",
                "every unit mission must be an existing nonempty file",
                {"unit_id": unit_id, "path": str(mission_path)},
            )
        outcomes = unit["outcomes"]
        if not isinstance(outcomes, list) or not outcomes:
            raise SupervisorError("MANIFEST_INVALID", f"{unit_field}.outcomes must be nonempty")
        normalized_outcomes: list[dict[str, Any]] = []
        outcome_names: set[str] = set()
        for outcome_index, outcome in enumerate(outcomes):
            outcome_field = f"{unit_field}.outcomes[{outcome_index}]"
            if not isinstance(outcome, dict):
                raise SupervisorError("MANIFEST_INVALID", f"{outcome_field} must be an object")
            require_keys(
                outcome,
                {"name", "commit_policy", "expected_change_paths", "verification_commands"},
                set(),
                outcome_field,
            )
            outcome_name = nonempty_text(outcome["name"], f"{outcome_field}.name", maximum=30).casefold()
            if outcome_name not in OUTCOME_NAMES or outcome_name in outcome_names:
                raise SupervisorError(
                    "MANIFEST_INVALID",
                    f"{outcome_field}.name must be one unique supported outcome",
                    {"supported": sorted(OUTCOME_NAMES)},
                )
            outcome_names.add(outcome_name)
            commit_policy = nonempty_text(
                outcome["commit_policy"], f"{outcome_field}.commit_policy", maximum=20
            ).casefold()
            if commit_policy not in COMMIT_POLICIES:
                raise SupervisorError("MANIFEST_INVALID", f"{outcome_field}.commit_policy is unsupported")
            paths = outcome["expected_change_paths"]
            if not isinstance(paths, list):
                raise SupervisorError("MANIFEST_INVALID", f"{outcome_field}.expected_change_paths must be an array")
            expected_paths = [
                normalize_relative(path, f"{outcome_field}.expected_change_paths[{path_index}]")
                for path_index, path in enumerate(paths)
            ]
            if len(expected_paths) != len(set(expected_paths)):
                raise SupervisorError("MANIFEST_INVALID", f"{outcome_field}.expected_change_paths has duplicates")
            if mission_relative in expected_paths:
                raise SupervisorError("MANIFEST_INVALID", "a frozen mission cannot be an expected source change")
            for expected_path in expected_paths:
                resolve_project_path(project_root, expected_path, must_exist=False)
            if commit_policy == "required" and not expected_paths:
                raise SupervisorError("MANIFEST_INVALID", "required commit outcomes need exact expected paths")
            if commit_policy == "forbidden" and expected_paths:
                raise SupervisorError("MANIFEST_INVALID", "forbidden commit outcomes cannot expect changed paths")
            commands = normalize_verification_commands(
                outcome["verification_commands"],
                f"{outcome_field}.verification_commands",
                project_root,
            )
            if outcome_name == "completed" and not commands:
                raise SupervisorError("MANIFEST_INVALID", "completed outcomes require deterministic verification")
            normalized_outcomes.append(
                {
                    "name": outcome_name,
                    "commit_policy": commit_policy,
                    "expected_change_paths": sorted(expected_paths),
                    "verification_commands": commands,
                }
            )
        if "completed" not in outcome_names:
            raise SupervisorError("MANIFEST_INVALID", f"{unit_field} must declare a completed outcome")
        normalized_units.append(
            {
                "id": unit_id,
                "description": str(unit.get("description") or "").strip(),
                "mission_path": mission_relative,
                "max_web_attempts": max_web_attempts,
                "context_refs": normalize_context_refs(unit.get("context_refs"), f"{unit_field}.context_refs"),
                "outcomes": normalized_outcomes,
            }
        )

    exact_unit_ids = authorization["exact_unit_ids"]
    if not isinstance(exact_unit_ids, list) or exact_unit_ids != unit_ids:
        raise SupervisorError(
            "AUTHORIZATION_SCOPE_MISMATCH",
            "authorization.exact_unit_ids must exactly match units in order",
            {"expected": unit_ids, "actual": exact_unit_ids},
        )
    live_limit = authorization["live_submission_limit"]
    authorized_attempt_total = sum(unit["max_web_attempts"] for unit in normalized_units)
    if (
        not isinstance(live_limit, int)
        or isinstance(live_limit, bool)
        or live_limit != authorized_attempt_total
    ):
        raise SupervisorError(
            "AUTHORIZATION_SCOPE_MISMATCH",
            "live_submission_limit must equal the sum of each unit's bounded web attempts",
            {"authorized_attempt_total": authorized_attempt_total, "actual": live_limit},
        )
    if any(
        outcome["commit_policy"] == "required"
        for unit in normalized_units
        for outcome in unit["outcomes"]
    ) and not authorization["local_commit"]:
        raise SupervisorError(
            "AUTHORIZATION_SCOPE_MISMATCH",
            "a required local commit outcome needs explicit local_commit authorization",
        )

    recording = payload["recording"]
    if not isinstance(recording, dict):
        raise SupervisorError("MANIFEST_INVALID", "recording must be an object")
    require_keys(recording, {"notion_required", "targets", "project_checkpoint_dir"}, set(), "recording")
    if not isinstance(recording["notion_required"], bool):
        raise SupervisorError("MANIFEST_INVALID", "recording.notion_required must be boolean")
    targets = normalize_context_refs(recording["targets"], "recording.targets")
    if not targets:
        raise SupervisorError("MANIFEST_INVALID", "recording.targets must be nonempty")
    if recording["notion_required"] and not any(target["kind"] == "notion" for target in targets):
        raise SupervisorError("MANIFEST_INVALID", "notion_required needs at least one Notion target")
    checkpoint_dir = normalize_relative(
        recording["project_checkpoint_dir"],
        "recording.project_checkpoint_dir",
    )
    resolve_project_path(project_root, checkpoint_dir, must_exist=False)

    return {
        "schema": MANIFEST_SCHEMA,
        "supervisor_id": supervisor_id,
        "description": str(payload.get("description") or "").strip(),
        "project_root": str(project_root),
        "role": ROLE,
        "supervisor": normalized_supervisor,
        "web": normalized_web,
        "authorization": {
            "request_fingerprint": request_fingerprint,
            "authorized_at": authorized_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "exact_unit_ids": unit_ids,
            "live_submission_limit": live_limit,
            "local_commit": authorization["local_commit"],
            "push": False,
            "deploy": False,
        },
        "recording": {
            "notion_required": recording["notion_required"],
            "targets": targets,
            "project_checkpoint_dir": checkpoint_dir,
        },
        "context_refs": normalize_context_refs(payload.get("context_refs"), "context_refs"),
        "units": normalized_units,
        "source_manifest": str(source_path.resolve(strict=True)),
    }
