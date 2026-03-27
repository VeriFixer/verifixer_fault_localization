#!/usr/bin/env python3
"""Repository health-check pipeline.

Runs, in order:
  1) Static type checking (Pyright, equivalent signal to Pylance diagnostics)
  2) Unit tests (pytest)
  3) Existing pos_test safeguard benchmark validation

Usage:
  python src/run_repo_health_check.py --clean-cache
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from run_pos_test_guard import find_repo_root


TYPE_CHECK_CMDS: list[tuple[str, list[str]]] = [
    ("type-check-src", ["pyright", "src"]),
    ("type-check-tests", ["pyright", "src/tests"]),
]
PYTEST_CMD: list[str] = ["pytest", "-q", "src/tests"]


@dataclass(frozen=True)
class StepResult:
    name: str
    command: list[str]
    return_code: int


def run_step(command: list[str], cwd: Path, step_name: str) -> StepResult:
    print(f"[repo-health] {step_name}: {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd)
    return StepResult(name=step_name, command=command, return_code=result.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run complete repository health checks: type checking, unit tests, "
            "and pos_test safeguard."
        )
    )
    parser.add_argument(
        "--dataset-tar",
        type=Path,
        default=Path("datasets/pos_test.tar.gz"),
        help="Path to the pos_test dataset tarball used by safeguard step.",
    )
    parser.add_argument(
        "--extracted-name",
        type=str,
        default="pos_test",
        help="Expected extracted top-level dataset directory name.",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Pass --clean-cache to src/run_pos_test_guard.py.",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Pass --sequential to src/run_pos_test_guard.py.",
    )
    parser.add_argument(
        "--skip-type-check",
        action="store_true",
        help="Skip static type-checking step.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip unit tests step.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on the first failed step (default: run all steps and summarize).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__))
    step_results: list[StepResult] = []

    if not args.skip_type_check:
        for step_name, command in TYPE_CHECK_CMDS:
            typecheck_result = run_step(command, repo_root, step_name)
            step_results.append(typecheck_result)
            if args.fail_fast and typecheck_result.return_code != 0:
                print("[repo-health] stopping early due to --fail-fast")
                return typecheck_result.return_code
    else:
        print("[repo-health] skipping type-check step")

    if not args.skip_tests:
        pytest_result = run_step(PYTEST_CMD, repo_root, "pytest")
        step_results.append(pytest_result)
        if args.fail_fast and pytest_result.return_code != 0:
            print("[repo-health] stopping early due to --fail-fast")
            return pytest_result.return_code
    else:
        print("[repo-health] skipping pytest step")

    safeguard_cmd: list[str] = [
        sys.executable,
        str(repo_root / "src" / "run_pos_test_guard.py"),
        "--dataset-tar",
        str(args.dataset_tar),
        "--extracted-name",
        args.extracted_name,
    ]
    if args.clean_cache:
        safeguard_cmd.append("--clean-cache")
    if args.sequential:
        safeguard_cmd.append("--sequential")

    safeguard_result = run_step(safeguard_cmd, repo_root, "pos_test-safeguard")
    step_results.append(safeguard_result)

    failed = [r for r in step_results if r.return_code != 0]

    print("[repo-health] summary:")
    for result in step_results:
        status = "PASS" if result.return_code == 0 else "FAIL"
        print(
            f" - {result.name}: {status} (exit={result.return_code}) :: {' '.join(result.command)}"
        )

    if failed:
        print(f"[repo-health] failed ({len(failed)} step(s) failed)", file=sys.stderr)
        return 1

    print("[repo-health] all checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"[repo-health] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
