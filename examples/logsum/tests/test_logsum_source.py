import pytest

from logsum.cli import load_allowed_levels
from logsum.core import LineParseError, summarize

def test_severity_resource_loads_from_the_source_tree():
    assert set(load_allowed_levels()) == {"INFO", "WARNING", "ERROR"}

def test_summarize_counts_each_severity():
    lines = ["INFO started\n", "ERROR failed\n", "ERROR abandoned\n"]
    assert summarize(lines, ["INFO", "WARNING", "ERROR"]) == {"INFO": 1, "WARNING": 0, "ERROR": 2}

def test_summarize_ignores_blank_lines():
    assert summarize(["\n", "INFO started\n", "  \n"], ["INFO"]) == {"INFO": 1}

def test_summarize_reports_the_line_number_of_a_bad_line():
    with pytest.raises(LineParseError, match="line 2"):
        summarize(["INFO started\n", "INVALID example\n"], ["INFO"])