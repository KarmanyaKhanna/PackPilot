import json
import shutil
import subprocess
from pathlib import Path

import pytest

from packpilot.cli import main

SNAP_NAME = "packpilot-logsum"
SNAP_TARGET = "packpilot-logsum.logsum"
EXAMPLE_CASES = Path(__file__).resolve().parents[1] / "examples" / "cases.json"

def snap_is_installed():
    if shutil.which("snap") is None:
        return False
    result = subprocess.run(["snap", "list", SNAP_NAME], capture_output=True, text=True)
    return result.returncode == 0

pytestmark = pytest.mark.skipif(not snap_is_installed(), reason=f"{SNAP_NAME} snap is not installed")

def test_installed_snap_passes_the_shared_suite(tmp_path):
    report_path = tmp_path / "snap.json"
    exit_code = main(
        ["verify", "snap", SNAP_TARGET, "--cases", str(EXAMPLE_CASES), "--report", str(report_path)]
    )
    assert exit_code == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["target_type"] == "snap"
    assert report["target"]["snap_name"] == SNAP_NAME
    assert report["target"]["snap_confinement"] == "strict"
    assert report["summary"] == {"passed": 7, "failed": 0}