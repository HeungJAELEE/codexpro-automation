from __future__ import annotations

"""CLI facade for durable Luna monitor/verify/record-only state.

The implementation is split by trust boundary. This facade intentionally
re-exports the small Python API used by tests and local operators.
"""

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from supervisor_core import SupervisorError, sha256_file  # noqa: E402
from supervisor_execution import pre_submit_failed, reserve, result_ready, submitted  # noqa: E402
from supervisor_records import block, record, record_remediation  # noqa: E402
from supervisor_store import prepare, status  # noqa: E402
from supervisor_verification import verify  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist Luna monitor/verify/record-only state for serialized Web GPT units."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "status"):
        command = subparsers.add_parser(name)
        command.add_argument("--manifest", required=True)

    reserve_parser = subparsers.add_parser("reserve")
    reserve_parser.add_argument("--manifest", required=True)
    reserve_parser.add_argument("--unit-id", required=True)
    reserve_parser.add_argument("--preview-sha256", required=True)

    submitted_parser = subparsers.add_parser("submitted")
    submitted_parser.add_argument("--manifest", required=True)
    submitted_parser.add_argument("--unit-id", required=True)
    submitted_parser.add_argument("--run-dir", required=True)
    submitted_parser.add_argument("--display-proof-file", required=True)

    failed_parser = subparsers.add_parser("pre-submit-failed")
    failed_parser.add_argument("--manifest", required=True)
    failed_parser.add_argument("--unit-id", required=True)
    failed_parser.add_argument("--run-dir", required=True)

    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("--manifest", required=True)
    result_parser.add_argument("--unit-id", required=True)
    result_parser.add_argument("--result-path", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True)
    verify_parser.add_argument("--unit-id", required=True)
    verify_parser.add_argument("--outcome", required=True)

    for command_name in ("record-remediation", "record"):
        record_parser = subparsers.add_parser(command_name)
        record_parser.add_argument("--manifest", required=True)
        record_parser.add_argument("--unit-id", required=True)
        record_parser.add_argument("--record-ref", action="append", default=[], required=True)
        record_parser.add_argument("--readback-fingerprint", required=True)
        record_parser.add_argument("--summary", required=True)

    block_parser = subparsers.add_parser("block")
    block_parser.add_argument("--manifest", required=True)
    block_parser.add_argument("--unit-id", required=True)
    block_parser.add_argument("--code", required=True)
    block_parser.add_argument("--message", required=True)
    block_parser.add_argument("--evidence-ref", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.manifest)
        elif args.command == "status":
            result = status(args.manifest)
        elif args.command == "reserve":
            result = reserve(args.manifest, args.unit_id, args.preview_sha256)
        elif args.command == "submitted":
            result = submitted(args.manifest, args.unit_id, args.run_dir, args.display_proof_file)
        elif args.command == "pre-submit-failed":
            result = pre_submit_failed(args.manifest, args.unit_id, args.run_dir)
        elif args.command == "result":
            result = result_ready(args.manifest, args.unit_id, args.result_path)
        elif args.command == "verify":
            result = verify(args.manifest, args.unit_id, args.outcome)
        elif args.command == "record-remediation":
            result = record_remediation(
                args.manifest,
                args.unit_id,
                args.record_ref,
                args.readback_fingerprint,
                args.summary,
            )
        elif args.command == "record":
            result = record(
                args.manifest,
                args.unit_id,
                args.record_ref,
                args.readback_fingerprint,
                args.summary,
            )
        elif args.command == "block":
            result = block(
                args.manifest,
                args.unit_id,
                args.code,
                args.message,
                args.evidence_ref,
            )
        else:
            raise SupervisorError("COMMAND_UNSUPPORTED", "unsupported supervisor command")
    except SupervisorError as exc:
        print(json.dumps(exc.envelope(), ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
