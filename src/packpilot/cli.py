from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from packpilot.cases import SuiteValidationError, load_suite
from packpilot.engine import FAILED, PASSED, run_suite
from packpilot.models import SetupResult
from packpilot.report import build_report, print_summary, report_passed, write_report
from packpilot.runners.wheel import (
    INSTALL_FAILED,
    VenvCreationError,
    WheelInstallError,
    WheelNotFoundError,
    describe_wheel,
    installed_wheel,
)

EXIT_PASSED = 0
EXIT_VERIFICATION_FAILED = 1
EXIT_INVALID_RUN = 2

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.handler(args)

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="packpilot",
        description="Verify the behaviour of installed application packages.",
    )
    parser.add_argument("--version", action="version", version="packpilot 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser("verify", help="verify an installed package against a test suite")
    targets = verify.add_subparsers(dest="target_type", required=True)

    wheel = targets.add_parser("wheel", help="install a wheel in a fresh venv and verify it")
    wheel.add_argument("wheel", type=Path, help="path to the .whl file")
    wheel.add_argument("--cases", type=Path, required=True, help="path to the JSON test suite")
    wheel.add_argument("--report", type=Path, help="where to write the JSON report")
    wheel.set_defaults(handler=_verify_wheel)

    return parser

def _verify_wheel(args: argparse.Namespace) -> int:
    try:
        suite = load_suite(args.cases)
        target = describe_wheel(args.wheel)
    except (SuiteValidationError, WheelNotFoundError) as e:
        return _invalid_run(str(e))
    target["entrypoint"] = suite.entrypoint

    results = None
    start = time.monotonic()
    try:
        with installed_wheel(args.wheel, suite.entrypoint) as run_target:
            setup = SetupResult(status=PASSED, duration_seconds=time.monotonic() - start)
            results = run_suite(
                suite,
                run_target.command_prefix,
                cwd=run_target.cwd,
                env=run_target.env,
            )
    except VenvCreationError as e:
        return _invalid_run(str(e))
    except WheelInstallError as e:
        setup = SetupResult(
            status=FAILED,
            duration_seconds=time.monotonic() - start,
            reason=INSTALL_FAILED,
            detail=str(e),
        )

    report = build_report("wheel", target, setup, results)
    print_summary(report)

    if args.report is not None:
        try:
            write_report(report, args.report)
        except OSError as e:
            return _invalid_run(f"could not write report to {args.report}: {e}")

    return EXIT_PASSED if report_passed(report) else EXIT_VERIFICATION_FAILED

def _invalid_run(message: str) -> int:
    print(f"packpilot: error: {message}", file=sys.stderr)
    return EXIT_INVALID_RUN

if __name__ == "__main__":
    raise SystemExit(main())