from collections.abc import Iterable, Sequence


class LineParseError(ValueError):
    def __init__(self, line_number: int, raw_line: str):
        self.line_number = line_number
        self.raw_line = raw_line
        super().__init__(f"line {line_number}: invalid severity or malformed line: {raw_line!r}")


def summarize(lines: Iterable[str], allowed_levels: Sequence[str]) -> dict[str, int]:
    counts = {level: 0 for level in allowed_levels}

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise LineParseError(line_number, raw_line)

        severity, _message = parts
        if severity not in counts:
            raise LineParseError(line_number, raw_line)

        counts[severity] += 1

    return counts
