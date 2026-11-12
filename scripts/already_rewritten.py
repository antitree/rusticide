#!/usr/bin/env python3
"""Checks whether this repo has already been rewritten once, ever."""
import os
import sys


def main() -> int:
    marker_path = sys.argv[1] if len(sys.argv) > 1 else ".rusticide-done"
    done = os.path.exists(marker_path)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"done={'true' if done else 'false'}\n")

    if done:
        print(f"Marker {marker_path} present — this repo has already been rewritten. No-op.")
    else:
        print(f"Marker {marker_path} not found — rewrite is still possible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
