import json
import sys
from contextlib import contextmanager

import pytest

from packpilot import cli
from packpilot.cli import main
from packpilot.models import ProcessResult, RunTarget
from packpilot.process import COMMAND_NOT_FOUND
from packpilot.runners import snap
from packpilot.runners.snap import (
    SnapTargetError,
    describe_snap,
    installed_snap,
    parse_snap_info,
    parse_snap_target,
)

SNAP_INFO = """\
name:    packpilot-logsum
summary: Summarize log severities from standard input
commands:
  - packpilot-logsum.logsum
snap-id:      unset
tracking:     -
installed:    0.1.0 (x1) 6.03MB -
  confinement:       strict
"""

SUITE = {
    "schema_version": 1,
    "entrypoint": "logsum",
    "cases": [
        {
            "name": "exits_cleanly",
            "args": [],
            "stdin": "",
            "timeout_seconds": 10,
            "expect": {"exit_code": 0},
        }
    ],
}

def fake_process(exit_code=0, stdout="", stderr="", failure=None):
    def run(*args, **kwargs):
        return ProcessResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=0.1,
            failure=failure,
        )

    return run

def write_suite(tmp_path):
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(SUITE), encoding="utf-8")
    return path

def test_parse_target_splits_snap_and_app():
    assert parse_snap_target("packpilot-logsum.logsum") == ("packpilot-logsum", "logsum")

@pytest.mark.parametrize(
    "target",
    ["logsum", "a.b.c", "../evil.logsum", "packpilot-logsum.", ".logsum", "name.app --flag", ""],
)
def test_parse_target_rejects_anything_else(target):
    with pytest.raises(SnapTargetError, match="snap-name.app-name"):
        parse_snap_target(target)

def test_parse_info_records_identity():
    assert parse_snap_info("packpilot-logsum", SNAP_INFO) == {
        "snap_name": "packpilot-logsum",
        "snap_version": "0.1.0",
        "snap_revision": "x1",
        "snap_confinement": "strict",
    }

def test_parse_info_rejects_a_snap_that_is_only_in_the_store():
    with pytest.raises(SnapTargetError, match="not installed"):
        parse_snap_info("hello", "name: hello\nsummary: from the store\n")

def test_describe_reports_a_missing_snap_command(monkeypatch):
    monkeypatch.setattr(snap, "run_command", fake_process(exit_code=None, failure=COMMAND_NOT_FOUND))
    with pytest.raises(SnapTargetError, match="could not query snapd"):
        describe_snap("packpilot-logsum.logsum")

def test_describe_reports_an_unknown_snap(monkeypatch):
    monkeypatch.setattr(snap, "run_command", fake_process(exit_code=1, stderr="no snap found\n"))
    with pytest.raises(SnapTargetError, match="no snap found"):
        describe_snap("packpilot-logsum.logsum")

def test_installed_snap_builds_the_command_and_cleans_up(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    with installed_snap("packpilot-logsum.logsum") as target:
        assert target.command_prefix == ["snap", "run", "packpilot-logsum.logsum"]
        assert "PYTHONPATH" not in target.env
        assert target.cwd.exists()
        cwd = target.cwd
    assert not cwd.exists()

def use_fake_snap(monkeypatch, tmp_path, code):
    @contextmanager
    def fake_installed_snap(target):
        yield RunTarget(command_prefix=[sys.executable, "-c", code], cwd=tmp_path, env={})

    monkeypatch.setattr(cli, "installed_snap", fake_installed_snap)
    monkeypatch.setattr(snap, "run_command", fake_process(stdout=SNAP_INFO))

def test_verify_snap_passes_and_records_the_snap_identity(monkeypatch, tmp_path):
    use_fake_snap(monkeypatch, tmp_path, "pass")
    report_path = tmp_path / "snap.json"
    exit_code = main(
        ["verify", "snap", "packpilot-logsum.logsum", "--cases", str(write_suite(tmp_path)), "--report", str(report_path)]
    )
    assert exit_code == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["target_type"] == "snap"
    assert report["target"]["snap_revision"] == "x1"
    assert report["target"]["snap_confinement"] == "strict"
    assert report["target"]["entrypoint"] == "logsum"
    assert report["summary"] == {"passed": 1, "failed": 0}

def test_verify_snap_exits_one_when_a_case_fails(monkeypatch, tmp_path):
    use_fake_snap(monkeypatch, tmp_path, "raise SystemExit(3)")
    exit_code = main(["verify", "snap", "packpilot-logsum.logsum", "--cases", str(write_suite(tmp_path))])
    assert exit_code == 1

def test_verify_snap_exits_two_when_the_app_does_not_match_the_suite(monkeypatch, tmp_path, capsys):
    use_fake_snap(monkeypatch, tmp_path, "pass")
    exit_code = main(["verify", "snap", "packpilot-logsum.other", "--cases", str(write_suite(tmp_path))])
    assert exit_code == 2
    assert "does not match suite entrypoint" in capsys.readouterr().err

def test_verify_snap_exits_two_for_a_bad_target(tmp_path, capsys):
    exit_code = main(["verify", "snap", "not-a-target", "--cases", str(write_suite(tmp_path))])
    assert exit_code == 2
    assert "snap-name.app-name" in capsys.readouterr().err