import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from packpilot.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CASES = REPO_ROOT / "examples" / "cases.json"
LOGSUM_TESTS = REPO_ROOT / "examples" / "logsum" / "tests"
RESOURCE = "logsum/data/severities.json"

def wheel_contents(wheel):
    with zipfile.ZipFile(wheel) as archive:
        return archive.namelist()

def verify(wheel, report_path):
    exit_code = main(
        ["verify", "wheel", str(wheel), "--cases", str(EXAMPLE_CASES), "--report", str(report_path)]
    )
    return exit_code, json.loads(report_path.read_text(encoding="utf-8"))

def test_broken_wheel_really_omits_the_resource(broken_logsum_wheel):
    assert RESOURCE not in wheel_contents(broken_logsum_wheel)

def test_fixed_wheel_contains_the_resource(logsum_wheel):
    assert RESOURCE in wheel_contents(logsum_wheel)

def test_source_tests_cannot_see_the_defect(broken_logsum_wheel):
    broken_source = broken_logsum_wheel.parents[1] / "source" / "src"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(LOGSUM_TESTS), "-q", "-p", "no:cacheprovider"],
        env={**os.environ, "PYTHONPATH": str(broken_source)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout

def test_broken_wheel_installs_but_fails_verification(broken_logsum_wheel, tmp_path):
    exit_code, report = verify(broken_logsum_wheel, tmp_path / "broken.json")
    assert exit_code == 1
    assert report["setup"]["status"] == "passed"
    assert report["summary"] == {"passed": 2, "failed": 5}

    failures = [case for case in report["cases"] if case["status"] == "failed"]
    assert {case["reason"] for case in failures} == {"exit_code_mismatch"}
    assert all("application resource error" in case["actual_stderr"] for case in failures)

def test_help_and_version_do_not_detect_the_defect(broken_logsum_wheel, tmp_path):
    _, report = verify(broken_logsum_wheel, tmp_path / "broken.json")
    passed = {case["name"] for case in report["cases"] if case["status"] == "passed"}
    assert passed == {"help", "version"}

def test_fixed_wheel_passes_the_same_suite(logsum_wheel, tmp_path):
    exit_code, report = verify(logsum_wheel, tmp_path / "fixed.json")
    assert exit_code == 0
    assert report["summary"] == {"passed": 7, "failed": 0}