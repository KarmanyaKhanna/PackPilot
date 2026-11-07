import json

import pytest

from packpilot.cases import SuiteValidationError, load_suite

VALID_SUITE = {
    "schema_version": 1,
    "entrypoint": "logsum",
    "cases": [
        {
            "name": "valid_input",
            "args": ["--json"],
            "stdin": "INFO service started\n",
            "timeout_seconds": 3,
            "expect": {"exit_code": 0, "stdout_json": {"INFO": 1}},
        }
    ],
}


def write_suite(tmp_path, data):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_valid_suite(tmp_path):
    path = write_suite(tmp_path, VALID_SUITE)
    suite = load_suite(path)
    assert suite.schema_version == 1
    assert suite.entrypoint == "logsum"
    assert len(suite.cases) == 1
    assert suite.cases[0].name == "valid_input"
    assert suite.cases[0].expect.exit_code == 0


def test_rejects_malformed_json(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(SuiteValidationError):
        load_suite(path)


def test_rejects_duplicate_case_names(tmp_path):
    data = json.loads(json.dumps(VALID_SUITE))
    data["cases"].append(dict(data["cases"][0]))
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError, match="duplicate"):
        load_suite(path)


def test_rejects_negative_timeout(tmp_path):
    data = json.loads(json.dumps(VALID_SUITE))
    data["cases"][0]["timeout_seconds"] = -1
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError, match="timeout_seconds"):
        load_suite(path)


def test_rejects_unknown_top_level_field(tmp_path):
    data = json.loads(json.dumps(VALID_SUITE))
    data["unexpected_field"] = True
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError, match="unknown"):
        load_suite(path)


def test_rejects_conflicting_stdout_expectations(tmp_path):
    data = json.loads(json.dumps(VALID_SUITE))
    data["cases"][0]["expect"]["stdout_contains"] = "INFO"
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError, match="stdout_json"):
        load_suite(path)


def test_rejects_boolean_exit_code(tmp_path):
    data = json.loads(json.dumps(VALID_SUITE))
    data["cases"][0]["expect"]["exit_code"] = True
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError):
        load_suite(path)


@pytest.mark.parametrize("version", [True, 1.0, "1", 2])
def test_rejects_invalid_schema_version(tmp_path, version):
    data = json.loads(json.dumps(VALID_SUITE))
    data["schema_version"] = version
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError, match="schema version"):
        load_suite(path)


@pytest.mark.parametrize(
    "entrypoint",
    ["../../bin/sh", "bin/logsum", "/bin/sh", "..", "-logsum", "logsum\n", "log sum", ""],
)
def test_rejects_entrypoint_that_is_not_a_plain_name(tmp_path, entrypoint):
    data = json.loads(json.dumps(VALID_SUITE))
    data["entrypoint"] = entrypoint
    path = write_suite(tmp_path, data)
    with pytest.raises(SuiteValidationError, match="entrypoint"):
        load_suite(path)


@pytest.mark.parametrize("entrypoint", ["logsum", "log-sum", "log_sum", "logsum.cli", "logsum2"])
def test_accepts_plain_entrypoint_names(tmp_path, entrypoint):
    data = json.loads(json.dumps(VALID_SUITE))
    data["entrypoint"] = entrypoint
    path = write_suite(tmp_path, data)
    assert load_suite(path).entrypoint == entrypoint
