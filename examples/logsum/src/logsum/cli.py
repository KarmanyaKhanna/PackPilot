import argparse
import sys
import json
from importlib import resources

from logsum.core import LineParseError, summarize

def load_allowed_levels() -> list[str]:
    try:
        resource = resources.files("logsum").joinpath("data", "severities.json")
        with resource.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ModuleNotFoundError) as e:
        print(f"logsum: application resource error: {e}", file=sys.stderr)
        raise SystemExit(1)

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="logsum",
        description="Summarize log severities from standard input.",
    )
    parser.add_argument(
        "--version", action = "version", version = "logsum 0.1.0"
    )
    parser.add_argument(
        "--json", action = "store_true", help = "print the summary as a JSON object"
    )
    args = parser.parse_args()

    allowed_levels = load_allowed_levels()
    lines = sys.stdin.readlines()

    try:
        counts = summarize(lines, allowed_levels)
    except LineParseError as e:
        print(f"logsum: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(counts))
    else:
        for level , count in counts.items():
            print(f"{level}: {count}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())