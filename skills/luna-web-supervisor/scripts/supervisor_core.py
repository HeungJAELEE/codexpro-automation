from __future__ import annotations

"""Shared contracts and trust-boundary primitives for Luna supervision."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterator
from urllib.parse import urlparse


MANIFEST_SCHEMA = "codex.luna-web-supervisor/1"
STATE_SCHEMA = "codex.luna-web-supervisor-state/1"
ROLE = "monitor-record-only"
WEB_CONTRACT = {
    "transport": "oracle-devspace",
    "mode": "orchestrator",
    "model": "GPT-5.6 Sol",
    "dispatcher_reasoning_level": "Very High",
    "visible_reasoning": "Extra High",
    "concurrency": 1,
}
SUPERVISOR_CONTRACT = {
    "model": "gpt-5.6-luna",
    "reasoning_effort": "high",
    "source_writes": False,
}
OUTCOME_NAMES = {"completed", "hold", "choice_issue"}
COMMIT_POLICIES = {"required", "optional", "forbidden"}
REMEDIABLE_CODES = {
    "VALIDATION_FAILED",
    "LOCAL_COMMIT_MISSING",
    "EXPECTED_CHANGE_MISSING",
    "OUTCOME_REQUIRES_REVERSION",
}
PHASES = {
    "UNIT_READY",
    "REMEDIATION_READY",
    "SUBMISSION_RESERVED",
    "WEB_ACTIVE",
    "RESULT_READY",
    "REMEDIATION_RECORDING_REQUIRED",
    "RECORDING_REQUIRED",
    "BLOCKED",
    "COMPLETE",
}
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
MODEL_PROOF = re.compile(r"\bgpt[- ]?5[.]6\s+sol\b", re.IGNORECASE)
REASONING_PROOF = re.compile(r"\bextra\s+high\b", re.IGNORECASE)


class SupervisorError(RuntimeError):
    def __init__(self, code: str, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}

    def envelope(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": str(self),
                "evidence": self.evidence,
            },
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be an ISO-8601 datetime")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise SupervisorError("MANIFEST_INVALID", f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SupervisorError("JSON_DUPLICATE_KEY", "JSON contains a duplicate key", {"key": key})
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SupervisorError("FILE_READ_FAILED", "could not read JSON file", {"path": str(path)}) from exc
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise SupervisorError(
            "JSON_INVALID",
            "file is not valid UTF-8 JSON",
            {"path": str(path), "line": exc.lineno, "column": exc.colno},
        ) from exc
    if not isinstance(value, dict):
        raise SupervisorError("JSON_OBJECT_REQUIRED", "top-level JSON value must be an object", {"path": str(path)})
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SupervisorError("FILE_HASH_FAILED", "could not hash file", {"path": str(path)}) from exc
    return digest.hexdigest()


def write_atomic(path: Path, value: Any) -> None:
    write_bytes_atomic(path, canonical_bytes(value))


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(canonical_bytes(event))
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def exclusive_lock(state_dir: Path) -> Iterator[None]:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "supervisor.lock"
    stream = lock_path.open("a+b")
    try:
        stream.seek(0)
        if stream.read(1) == b"":
            stream.seek(0)
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise SupervisorError(
                    "SUPERVISOR_LOCKED",
                    "another supervisor command is active for this batch",
                    {"lock": str(lock_path)},
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise SupervisorError(
                    "SUPERVISOR_LOCKED",
                    "another supervisor command is active for this batch",
                    {"lock": str(lock_path)},
                ) from exc
        yield
    finally:
        try:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def require_keys(value: dict[str, Any], required: set[str], optional: set[str], field: str) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing or unknown:
        raise SupervisorError(
            "MANIFEST_INVALID",
            f"{field} has missing or unsupported fields",
            {"field": field, "missing": missing, "unknown": unknown},
        )


def nonempty_text(value: Any, field: str, *, maximum: int = 1000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be nonempty text")
    result = value.strip()
    if len(result) > maximum or "\x00" in result:
        raise SupervisorError("MANIFEST_INVALID", f"{field} is too long or contains a null byte")
    return result


def safe_id(value: Any, field: str) -> str:
    result = nonempty_text(value, field, maximum=80).casefold()
    if SAFE_ID.fullmatch(result) is None:
        raise SupervisorError(
            "MANIFEST_INVALID",
            f"{field} must use lowercase letters, numbers, dot, underscore, or hyphen",
        )
    return result


def normalize_relative(value: Any, field: str) -> str:
    raw = nonempty_text(value, field, maximum=500).replace("\\", "/")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in path.parts[0]
        or any(character in raw for character in "*?[]")
        or any(ord(character) < 32 for character in raw)
    ):
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be one exact relative path", {"value": raw})
    return path.as_posix()


def resolve_project_path(project_root: Path, relative: str, *, must_exist: bool) -> Path:
    candidate = (project_root / Path(*PurePosixPath(relative).parts)).resolve(strict=must_exist)
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise SupervisorError(
            "PATH_OUTSIDE_PROJECT",
            "manifest path escapes the exact project root",
            {"path": str(candidate), "project_root": str(project_root)},
        ) from exc
    return candidate


def normalize_url(value: Any, field: str) -> str:
    result = nonempty_text(value, field, maximum=1000)
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be an https URL")
    return result


def normalize_context_refs(values: Any, field: str) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 20:
        raise SupervisorError("MANIFEST_INVALID", f"{field} must be an array of at most 20 references")
    result: list[dict[str, str]] = []
    for index, item in enumerate(values):
        item_field = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise SupervisorError("MANIFEST_INVALID", f"{item_field} must be an object")
        require_keys(item, {"kind", "url", "purpose"}, set(), item_field)
        kind = nonempty_text(item["kind"], f"{item_field}.kind", maximum=20).casefold()
        if kind not in {"notion", "web"}:
            raise SupervisorError("MANIFEST_INVALID", f"{item_field}.kind must be notion or web")
        url = normalize_url(item["url"], f"{item_field}.url")
        if kind == "notion" and urlparse(url).netloc.casefold() not in {
            "app.notion.com",
            "www.notion.so",
            "notion.so",
        }:
            raise SupervisorError("MANIFEST_INVALID", f"{item_field}.url is not a Notion URL")
        result.append(
            {
                "kind": kind,
                "url": url,
                "purpose": nonempty_text(item["purpose"], f"{item_field}.purpose", maximum=300),
            }
        )
    return result
