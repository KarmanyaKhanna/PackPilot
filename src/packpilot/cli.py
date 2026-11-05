import argparse

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="packpilot",
        description = "Verify the behaviour of installed application packages.",
    )

    parser.add_argument(
        "--version", action = "version", version = "packpilot 0.1.0"
    )
    parser.parse_args()
    parser.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())