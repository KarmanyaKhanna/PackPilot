from __future__ import annotations

import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from packpilot.models import RunTarget
from packpilot.process import clean_environment, run_command

SNAP_INFO_TIMEOUT_SECONDS = 30
_SNAP_TARGET = re.compile(r"([a-z0-9][a-z0-9-]*)\.([a-zA-Z0-9][a-zA-Z0-9-]*)")
_INSTALLED_LINE = re.compile(r"^installed:\s+(\S+)\s+\((\S+)\)", re.MULTILINE)
_CONFINEMENT_LINE = re.compile(r"^\s*confinement:\s+(\S+)", re.MULTILINE)

class SnapTargetError(ValueError):
    pass

def parse_snap_target(target: str) -> tuple[str, str]:
    match = _SNAP_TARGET.fullmatch(target)
    if match is None:
        raise SnapTargetError(f"snap target must look like snap-name.app-name, got {target!r}")
    return match.group(1), match.group(2)

def parse_snap_info(snap_name: str, info: str) -> dict[str, str]:
    installed = _INSTALLED_LINE.search(info)
    if installed is None:
        raise SnapTargetError(f"snap {snap_name!r} is not installed")
    confinement = _CONFINEMENT_LINE.search(info)
    return {
        "snap_name": snap_name,
        "snap_version": installed.group(1),
        "snap_revision": installed.group(2),
        "snap_confinement": confinement.group(1) if confinement is not None else "unknown",
    }

def describe_snap(target: str) -> dict[str, str]:
    snap_name, app_name = parse_snap_target(target)
    result = run_command(
        ["snap", "info", "--verbose", snap_name],
        stdin="",
        timeout_seconds=SNAP_INFO_TIMEOUT_SECONDS,
    )
    if result.failure is not None:
        raise SnapTargetError(f"could not query snapd ({result.failure}): {result.stderr}")
    if result.exit_code != 0:
        raise SnapTargetError(f"snap {snap_name!r} is not available: {result.stderr.strip()}")
    return {**parse_snap_info(snap_name, result.stdout), "snap_app": app_name}

@contextmanager
def installed_snap(target: str) -> Iterator[RunTarget]:
    with tempfile.TemporaryDirectory(prefix="packpilot-") as temp_dir:
        yield RunTarget(
            command_prefix=["snap", "run", target],
            cwd=Path(temp_dir).resolve(),
            env=clean_environment(),
        )