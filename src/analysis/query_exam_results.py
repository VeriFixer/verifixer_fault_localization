from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from fl_eval.metrics.scoring import (
    compute_exam_score_method_scope,
    compute_exam_score_one_file,
    load_from_file_output,
)
from logging_config import get_logger
from evaluators.eval_model_common import (
    TECHNIQUE_MAP,
    build_mutation_context,
    setup_evaluation,
)

logger = get_logger(__name__)


Comparator = Callable[[float, float], bool]


@dataclass(frozen=True)
class QueryMatch:
    technique: str
    mutant_name: str
    mutant_path: str
    file_exam: float
    method_exam: float
    file_found: bool
    method_found: bool
    predictions_file: list[int]


_COMPARATORS: dict[str, Comparator] = {
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    "==": lambda left, right: left == right,
}


def _parse_techniques(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return sorted(TECHNIQUE_MAP.keys())

    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [name for name in parsed if name not in TECHNIQUE_MAP]
    if unknown:
        raise ValueError(f"Unknown techniques: {unknown}. Available: {sorted(TECHNIQUE_MAP.keys())}")

    return parsed


def _match_threshold(value: float, op: str, threshold: float) -> bool:
    comparator = _COMPARATORS.get(op)
    if comparator is None:
        raise ValueError(f"Unsupported comparator: {op}")
    return comparator(value, threshold)


def _query_single_technique(
    dataset_dir: Path,
    technique_name: str,
    scope: str,
    op: str,
    threshold: float,
) -> list[QueryMatch]:
    setup_result = setup_evaluation(technique_name, dataset_dir, to_validate_dataset=False)
    if setup_result is None:
        logger.warning("Skipping %s due to setup failure.", technique_name)
        return []

    fl_technique, killed_dir, original_dir = setup_result
    diff_paths = sorted(killed_dir.glob("*.txt"))

    matches: list[QueryMatch] = []
    for diff_path in diff_paths:
        context = build_mutation_context(diff_path, killed_dir, original_dir)
        if context is None:
            continue

        try:
            predictions = load_from_file_output(fl_technique, context.gtruth, dataset_dir)
        except Exception as e:
            logger.debug("Skipping %s/%s due to cache load failure: %s", technique_name, context.mutant_dfy_path.name, e)
            continue

        file_exam = compute_exam_score_one_file(
            predictions,
            context.gtruth.ground_truth,
            context.gtruth.startLine,
            context.gtruth.endLine,
            str(context.mutant_dfy_path),
            suppress_warnings=fl_technique.suppress_scope_warnings,
        )

        method_exam = file_exam
        if context.gtruth.method_start <= context.gtruth.ground_truth <= context.gtruth.method_end:
            method_exam = compute_exam_score_method_scope(
                predictions,
                context.gtruth.ground_truth,
                context.gtruth.method_start,
                context.gtruth.method_end,
                str(context.mutant_dfy_path),
                suppress_warnings=fl_technique.suppress_scope_warnings,
            )

        scoped_value = file_exam.score if scope == "file" else method_exam.score
        if not _match_threshold(scoped_value, op, threshold):
            continue

        matches.append(
            QueryMatch(
                technique=technique_name,
                mutant_name=context.mutant_dfy_path.name,
                mutant_path=str(context.mutant_dfy_path),
                file_exam=file_exam.score,
                method_exam=method_exam.score,
                file_found=file_exam.found,
                method_found=method_exam.found,
                predictions_file=predictions,
            )
        )

    return matches


def query_exam_results(
    dataset_dir: Path,
    techniques: list[str],
    scope: str,
    op: str,
    threshold: float,
) -> list[QueryMatch]:
    all_matches: list[QueryMatch] = []
    for technique in techniques:
        all_matches.extend(_query_single_technique(dataset_dir, technique, scope, op, threshold))

    all_matches.sort(key=lambda item: (item.technique, item.mutant_name))
    return all_matches


def _print_matches(matches: list[QueryMatch], output: str) -> None:
    if output == "names":
        for item in matches:
            print(item.mutant_name)
        return

    if output == "json":
        print(json.dumps([asdict(item) for item in matches], indent=2))
        return

    # csv
    print("technique,mutant_name,mutant_path,file_exam,method_exam,file_found,method_found")
    for item in matches:
        print(
            f"{item.technique},{item.mutant_name},{item.mutant_path},"
            f"{item.file_exam:.6f},{item.method_exam:.6f},{item.file_found},{item.method_found}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query cached FL results by EXAM threshold and print matching mutants."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Dataset directory containing killed/original folders.",
    )
    parser.add_argument(
        "--techniques",
        type=str,
        default=None,
        help="Comma-separated techniques to query (default: all techniques).",
    )
    parser.add_argument(
        "--scope",
        type=str,
        choices=["file", "method"],
        default="file",
        help="EXAM scope to filter on.",
    )
    parser.add_argument(
        "--op",
        type=str,
        choices=list(_COMPARATORS.keys()),
        default=">",
        help="Comparison operator for threshold filtering.",
    )
    parser.add_argument(
        "--value",
        type=float,
        required=True,
        help="Threshold value for EXAM filtering.",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["names", "json", "csv"],
        default="names",
        help="Output format. 'names' prints matching mutant filenames only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.dataset.exists():
        raise FileNotFoundError(f"Dataset path not found: {args.dataset}")

    techniques = _parse_techniques(args.techniques)
    matches = query_exam_results(
        dataset_dir=args.dataset,
        techniques=techniques,
        scope=args.scope,
        op=args.op,
        threshold=args.value,
    )

    _print_matches(matches, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
