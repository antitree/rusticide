#!/usr/bin/env python3
"""Runs a single one-shot Claude Code session that rewrites the repo.

Target language: Rust, unless the repo is already Rust (root Cargo.toml
present), in which case the target is Erlang. This is one bounded
invocation — retries, if the model needs them, happen as ordinary tool
calls (running cargo/rebar3, reading the error, fixing it) inside this one
session, not as separate re-invocations of this script.

Whether or not the build ends up passing, the session must leave the repo
in a pushable state: it writes the marker file itself as its last step, and
push_to_main.sh pushes whatever is on disk afterward, pass or fail.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(".").resolve()


def detect_target_language() -> str:
    if (REPO_ROOT / "Cargo.toml").exists():
        return "erlang"
    return "rust"


def build_prompt(target: str, marker_path: str) -> str:
    if target == "rust":
        build_cmds = "cargo build && cargo test"
        scaffold_hint = "Create a Cargo.toml at the repo root and an idiomatic Rust crate layout (src/main.rs or src/lib.rs plus modules)."
    else:
        build_cmds = "rebar3 compile && rebar3 eunit"
        scaffold_hint = "Create a rebar.config at the repo root and an idiomatic Erlang/OTP application layout (src/, include/)."

    return f"""You are rewriting this entire repository's source code into {target.capitalize()}.
This is a one-shot, unattended task. You will not be asked any questions and no
human will review your output before it is pushed to the main branch. Do the
best job you can within this single session.

Rules:
- Rewrite ALL application source code into {target.capitalize()}, preserving functional
  behavior as closely as you can determine from the existing code, tests, and
  README. {scaffold_hint}
- Delete the old source files once they are superseded by your rewrite, so the
  repo ends up as a working {target.capitalize()} project, not a mix of old and new.
- Keep non-code files that still make sense (README, LICENSE, CI config you
  update to build the new project, existing docs) and update anything that
  references the old build/run commands.
- Attempt to build the result yourself using: {build_cmds}
- If the build or tests fail, read the error and fix it, and try again, as many
  times as you judge useful within this session. You do not need permission to
  keep iterating.
- You will NOT get another turn after this. If you cannot get it fully working,
  leave the closest-to-working state you have rather than reverting everything.
- As your final action, create an empty marker file at `{marker_path}` to record
  that this rewrite happened. Do this unconditionally, even if the build is not
  fully passing.
- Do not ask the user any clarifying questions. Make your own reasonable
  judgment calls and proceed.
"""


def main() -> int:
    marker_path = ".rusticide-done"
    if "--marker-path" in sys.argv:
        marker_path = sys.argv[sys.argv.index("--marker-path") + 1]

    target = detect_target_language()
    prompt = build_prompt(target, marker_path)

    print(f"Target language: {target}")
    print("Launching one-shot Claude Code session...")

    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "bypassPermissions",
        ],
        cwd=str(REPO_ROOT),
        env=os.environ,
    )

    # Belt-and-suspenders: if the agent didn't write the marker itself
    # (e.g. it crashed instead of finishing), write it now. The rewrite
    # happens at most once per repo regardless of how it went.
    marker = REPO_ROOT / marker_path
    if not marker.exists():
        marker.write_text(
            f"Rewrite attempted, target={target}, "
            f"claude_exit_code={result.returncode}\n"
        )

    print(f"Claude Code session exited with code {result.returncode}.")
    print("Proceeding to push regardless of outcome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
