from __future__ import annotations

"""Read-only Oracle incident classification used by supervisor transitions."""

import importlib.util
from pathlib import Path
import sys

from supervisor_core import SupervisorError


def build_incident_packet(run_dir: Path) -> dict[str, object]:
    module_path = Path(__file__).resolve().parents[3] / "bin" / "chatgpt_oracle_incident.py"
    spec = importlib.util.spec_from_file_location("luna_supervisor_oracle_incident", module_path)
    if spec is None or spec.loader is None:
        raise SupervisorError(
            "INCIDENT_RUNTIME_UNAVAILABLE",
            "the installed Oracle incident classifier is unavailable",
            {"path": str(module_path)},
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.validate_packet(module.build_packet(run_dir))
