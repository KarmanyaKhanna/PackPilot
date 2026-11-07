from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from packpilot.engine import PASSED
from packpilot.models import SetupResult, VerificationReport

REPORT_SCHEMA_VERSION = 1


def build_report(
    target_type: str,
    target: dict[str, str],
    setup: SetupResult,
    results: VerificationReport | None,
) -> dict:
    cases = results.cases if results is not None else []
    summary = results.summary if results is not None else {"passed": 0, "failed": 0}

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "target_type": target_type,
        "target": target,
        "environment": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "runner_python_version": platform.python_version(),
            "runner_python_executable": sys.executable,
        },
        "setup": asdict(setup),
        "summary": summary,
        "cases": [asdict(case) for case in cases],
    }


def report_passed(report: dict) -> bool:
    return report["setup"]["status"] == PASSED and report["summary"]["failed"] == 0


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def print_summary(report: dict) -> None:
    setup = report["setup"]
    if setup["status"] != PASSED:
        print(f"SETUP FAILED: {setup['reason']}: {setup['detail']}", file=sys.stderr)

    for case in report["cases"]:
        if case["status"] == PASSED:
            print(f"PASS {case['name']}", file=sys.stderr)
            continue
        print(f"FAIL {case['name']}: {case['reason']}: {case['detail']}", file=sys.stderr)
        if case["actual_stderr"]:
            print(f"  stderr: {case['actual_stderr'].strip()}", file=sys.stderr)

    summary = report["summary"]
    print(f"{summary['passed']} passed, {summary['failed']} failed", file=sys.stderr)
