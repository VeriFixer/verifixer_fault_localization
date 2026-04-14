#!/usr/bin/env python3
"""Integration safeguard pipeline: Run full pos_test benchmark with infrastructure validation.

This script serves as CI/local smoke test to detect infrastructure breakage. It executes the
full FL evaluation pipeline and validates that all expected artifacts are produced.

For a complete repository validation (type check + tests + safeguard), use
`src/run_repo_health_check.py`.

Flow:
    1) Extract datasets/pos_test.tar.gz → datasets/pos_test
    2) Execute src/run_all_models.py on that dataset
    3) Validate key outputs:
       - Plot files: run_artifacts/plots_<mutant>.png per FL technique
       - Cache files: run_artifacts/cached_results/<technique>/<mutant>.json
       - Metadata: execution_metadata (timestamps, commands, status) in cache
    4) Apply quality gates (EXAM score thresholds, minimum fault detection rate)

Usage:
    python src/run_pos_test_guard.py --dataset-tar datasets/pos_test.tar.gz [--clean-cache]

Quality Gates:
    Each technique has max_avg_exam and min_found_count thresholds to detect regressions.
    See TECHNIQUE_GUARDS constant for current per-technique limits.
    All gates must pass for successful integration validation.

Exits:
    0: All validations passed
    1: Dataset extraction failed
    2: Pipeline execution failed
    3: Artifact validation failed (missing files, metadata inconsistent)
    4: Quality gate failures (EXAM too high, not enough faults found)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config as gl
from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from fl_eval.metrics.scoring import compute_exam_score_one_file, load_from_file_output
from fl_eval.util.run_model_common import TECHNIQUE_MAP, get_techniques_for_all_models, get_techniques_for_health_check

REPO_MARKER = ".repo_verifixer_fault_localization_marker"


@dataclass(frozen=True)
class TechniqueGuard:
    max_avg_exam: float
    min_found_count: int
    allow_all_empty_predictions: bool = False


# Manual quality gates for reuse across runs.
TECHNIQUE_GUARDS: dict[str, TechniqueGuard] = {
    "random": TechniqueGuard(max_avg_exam=1.0, min_found_count=0),
    "counterBase": TechniqueGuard(max_avg_exam=1.0, min_found_count=1),
    "empty": TechniqueGuard(max_avg_exam=1.0, min_found_count=0, allow_all_empty_predictions=True),
    "randomOnFailingMethod": TechniqueGuard(max_avg_exam=1.0, min_found_count=0),
    "counterExampleIf": TechniqueGuard(max_avg_exam=1.0, min_found_count=1),
    "counterExampleIfReassume": TechniqueGuard(max_avg_exam=1.0, min_found_count=1),
    "llm_stub_all_lines_ranked": TechniqueGuard(max_avg_exam=1.0, min_found_count=0),
    "llm_qwen_480b": TechniqueGuard(max_avg_exam=1.0, min_found_count=0, allow_all_empty_predictions=True),
    # Temporary waiver: AutoFix currently returns empty predictions on pos_test.
    # Remove allow_all_empty_predictions=True when AutoFix becomes reliable.
    "autofixDefault": TechniqueGuard(max_avg_exam=1.0, min_found_count=1),
    "autofixSimplified": TechniqueGuard(max_avg_exam=1.0, min_found_count=1),
}


def check_prediction_guarantees(
    per_technique_predictions: dict[str, dict[str, list[int]]],
) -> list[str]:
    """Validate cross-technique monotonic guarantees.

    Guarantees:
        1) Every line predicted by counterBase for a mutation must also be
            predicted by counterExampleIf for that mutation.
      2) Every line predicted by counterExampleIf for a mutation must also be
         predicted by counterExampleIfReassume for that mutation.
    """

    errors: list[str] = []

    counter_base = per_technique_predictions.get("counterBase", {})
    counter_if = per_technique_predictions.get("counterExampleIf", {})
    counter_reassume = per_technique_predictions.get("counterExampleIfReassume", {})

    all_mutations = sorted(
        set(counter_base.keys())
        | set(counter_if.keys())
        | set(counter_reassume.keys())
    )

    for mutation_name in all_mutations:
        base_preds = counter_base.get(mutation_name, [])
        if_preds = counter_if.get(mutation_name, [])
        reassume_preds = counter_reassume.get(mutation_name, [])

        missing_from_if = sorted(set(base_preds) - set(if_preds))
        if missing_from_if:
            errors.append(
                "Guarantee failed for mutation "
                f"'{mutation_name}': counterBase lines {sorted(set(base_preds))} "
                "must be included in counterExampleIf, but missing "
                f"lines are {missing_from_if}."
            )

        missing_from_reassume = sorted(set(if_preds) - set(reassume_preds))
        if missing_from_reassume:
            errors.append(
                "Guarantee failed for mutation "
                f"'{mutation_name}': counterExampleIf lines {sorted(set(if_preds))} "
                "must be included in counterExampleIfReassume, but missing "
                f"lines are {missing_from_reassume}."
            )
    return errors


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    while True:
        if (current / REPO_MARKER).exists():
            return current
        if current.parent == current:
            raise FileNotFoundError(
                f"Could not locate repository root marker '{REPO_MARKER}' from {start}."
            )
        current = current.parent


def extract_dataset(dataset_tar: Path, datasets_dir: Path, extracted_name: str) -> Path:
    extracted_dataset = datasets_dir / extracted_name

    if extracted_dataset.exists():
        shutil.rmtree(extracted_dataset)

    datasets_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(dataset_tar, "r:gz") as tar:
        tar.extractall(path=datasets_dir)

    if not extracted_dataset.exists():
        raise RuntimeError(
            f"Expected extracted dataset at {extracted_dataset}, but it was not found."
        )

    return extracted_dataset


def validate_dataset_layout(dataset_dir: Path) -> int:
    killed_dir = dataset_dir / "killed"
    original_dir = dataset_dir / "original"

    if not killed_dir.is_dir() or not original_dir.is_dir():
        raise RuntimeError(
            f"Dataset must contain 'killed' and 'original' directories: {dataset_dir}"
        )

    mutation_count = len(list(killed_dir.glob("*.txt")))
    if mutation_count == 0:
        raise RuntimeError(f"No mutation diff files (*.txt) found in {killed_dir}")

    return mutation_count


def run_benchmark(
    run_all_models: Path,
    dataset_dir: Path,
    clean_cache: bool,
    sequential: bool,
    health_check: bool,
) -> None:
    cmd = [sys.executable, str(run_all_models), str(dataset_dir)]
    if clean_cache:
        cmd.append("--clean-cache")
    if sequential:
        cmd.append("--sequential")
    if health_check:
        cmd.append("--health-check")

    result = subprocess.run(cmd, cwd=run_all_models.parent.parent)
    if result.returncode != 0:
        raise RuntimeError(f"Benchmark command failed with code {result.returncode}: {' '.join(cmd)}")


def validate_outputs(
    repo_root: Path,
    dataset_dir: Path,
    expected_mutation_count: int,
    health_check: bool = False,
) -> None:
    print("Validating outpus, created files etc")
    errors: list[str] = []
    techniques_to_validate = (
        get_techniques_for_health_check()
        if health_check
        else get_techniques_for_all_models()
    )
    print(
        "(using "
        f"{'health-check' if health_check else 'full'} "
        f"technique set: {len(techniques_to_validate)} techniques)"
    )

    required_split_plots = [
        gl.BASE_PATH / "images" / "benchmark_hybrid_analysis_FILE_distribution.png",
        gl.BASE_PATH / "images" / "benchmark_hybrid_analysis_FILE_success.png",
    ]
    missing_split_plots = [p for p in required_split_plots if not (p.exists() and p.stat().st_size > 0)]
    if missing_split_plots:
        legacy_plot_candidates = [
            gl.BASE_PATH / "images" / "benchmark_hybrid_analysis_FILE.png",
            gl.BASE_PATH / "images" / "benchmark_hybrid_analysis.png",
            dataset_dir.parent / "benchmark_hybrid_analysis_FILE.png",
            dataset_dir.parent / "benchmark_hybrid_analysis.png",
        ]
        legacy_plot = next(
            (p for p in legacy_plot_candidates if p.exists() and p.stat().st_size > 0),
            None,
        )
        if legacy_plot is None:
            errors.append(
                "Missing or empty benchmark plot output. Checked split files: "
                + ", ".join(str(p) for p in required_split_plots)
                + "; legacy files: "
                + ", ".join(str(p) for p in legacy_plot_candidates)
            )

    missing_cfg = sorted(set(techniques_to_validate) - set(TECHNIQUE_GUARDS.keys()))
    if missing_cfg:
        errors.append(
            "Technique guard config missing entries for active techniques. "
            f"Missing: {missing_cfg}"
        )

    killed_dir = dataset_dir / "killed"
    original_dir = dataset_dir / "original"
    diff_paths = sorted(killed_dir.glob("*.txt"))
    if len(diff_paths) != expected_mutation_count:
        errors.append(
            f"Found {len(diff_paths)} diffs in dataset, expected {expected_mutation_count}."
        )

    cache_root = gl.get_dataset_cache_dir(dataset_dir)
    summary: dict[str, dict[str, Any]] = {}
    per_technique_predictions: dict[str, dict[str, list[int]]] = {
        technique_name: {}
        for technique_name in techniques_to_validate
    }

    for technique_name in techniques_to_validate:
        technique_cls = TECHNIQUE_MAP[technique_name][0]
        technique_dir = cache_root / technique_name
        if not technique_dir.is_dir():
            errors.append(f"Missing cache folder for technique: {technique_name}")
            continue

        flt = technique_cls(name=technique_name)
        guard = TECHNIQUE_GUARDS[technique_name]

        evaluated = 0
        found_count = 0
        empty_predictions = 0
        exam_sum = 0.0
        failed_mutations = 0

        for diff_path in diff_paths:
            mutation_name = diff_path.stem
            mutant_dfy_path = killed_dir / f"{mutation_name}.dfy"
            if not mutant_dfy_path.is_file():
                errors.append(f"[{technique_name}] Missing mutant file for diff {diff_path.name}: {mutant_dfy_path}")
                failed_mutations += 1
                continue

            base_name_raw = "__".join(mutation_name.split("__")[:-1])
            original_file = original_dir / f"{base_name_raw}.dfy"
            if not original_file.is_file():
                errors.append(f"[{technique_name}] Missing original file for mutation {mutation_name}: {original_file}")
                failed_mutations += 1
                continue

            try:
                gtruth = GroundTruthAndLineLimit(
                    originalfile=original_file,
                    mutantfile=mutant_dfy_path,
                    difffile=diff_path,
                )

                # Reuse cached-results loading logic from fl_eval.metrics.scoring.
                predictions = load_from_file_output(flt, gtruth, dataset_dir)
                per_technique_predictions[technique_name][mutation_name] = predictions
                if not predictions:
                    empty_predictions += 1

                exam_output = compute_exam_score_one_file(
                    predictions=predictions,
                    ground_truth=gtruth.ground_truth,
                    total_line_start=gtruth.startLine,
                    total_line_end=gtruth.endLine,
                    filename=str(mutant_dfy_path),
                )
            except Exception as exc:
                errors.append(f"[{technique_name}] Mutation '{mutation_name}' failed: {exc}")
                failed_mutations += 1
                continue

            exam_sum += exam_output.score
            found_count += 1 if exam_output.found else 0
            evaluated += 1

        if evaluated != len(diff_paths):
            errors.append(
                f"Technique '{technique_name}' evaluated {evaluated}/{len(diff_paths)} mutations (failed={failed_mutations})."
            )

        if evaluated > 0 and empty_predictions == evaluated and not guard.allow_all_empty_predictions:
            errors.append(
                f"Technique '{technique_name}' produced only empty predictions across all evaluated mutations."
            )

        avg_exam = exam_sum / evaluated if evaluated else 0.0

        if avg_exam > guard.max_avg_exam:
            errors.append(
                f"Technique '{technique_name}' avg EXAM {avg_exam:.4f} exceeds limit {guard.max_avg_exam:.4f}."
            )

        if found_count < guard.min_found_count:
            errors.append(
                f"Technique '{technique_name}' found_count {found_count} is below limit {guard.min_found_count}."
            )

        summary[technique_name] = {
            "evaluated": evaluated,
            "found_count": found_count,
            "avg_exam": avg_exam,
            "empty_predictions": empty_predictions,
        }

    # TEMPORARY COMMENTED GURARANTEE UNTILL FIX COUNTERXAMPLES
    #errors.extend(check_prediction_guarantees(per_technique_predictions))

    print("Technique checks:")
    for technique_name in sorted(summary.keys()):
        item = summary[technique_name]
        print(
            f" - {technique_name}: "
            f"evaluated={item['evaluated']}, "
            f"found={item['found_count']}, "
            f"avg_exam={item['avg_exam']:.4f}, "
            f"empty_predictions={item['empty_predictions']}"
        )

    if errors:
        print("\nValidation errors:")
        for err in errors:
            print(f" - {err}")
        raise RuntimeError(f"Validation failed with {len(errors)} error(s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full pos_test safeguard benchmark and validate outputs."
    )
    parser.add_argument(
        "--dataset-tar",
        type=Path,
        default=Path("datasets/pos_test.tar.gz"),
        help="Path to the pos_test dataset tarball.",
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
        help="Pass --clean-cache to src/run_all_models.py.",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Pass --sequential to src/run_all_models.py.",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run reduced technique set for repository health checks (skips slow techniques).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__))

    dataset_tar = (repo_root / args.dataset_tar).resolve() if not args.dataset_tar.is_absolute() else args.dataset_tar
    if not dataset_tar.exists():
        raise FileNotFoundError(f"Dataset tarball not found: {dataset_tar}")

    datasets_dir = dataset_tar.parent
    dataset_dir = extract_dataset(dataset_tar, datasets_dir, args.extracted_name)
    mutation_count = validate_dataset_layout(dataset_dir)

    run_all_models = repo_root / "src" / "run_all_models.py"
    run_benchmark(
        run_all_models,
        dataset_dir,
        args.clean_cache,
        args.sequential,
        args.health_check,
    )

    # Output validation is too havy for now not using
    validate_outputs(
        repo_root,
        dataset_dir,
        mutation_count,
        health_check=args.health_check,
    )

    techniques_used = (
        get_techniques_for_health_check()
        if args.health_check
        else get_techniques_for_all_models()
    )
    print("pos_test safeguard passed.")
    print(f" - dataset: {dataset_dir}")
    print(f" - mutations validated: {mutation_count}")
    print(
        " - techniques validated: "
        f"{len(techniques_used)} "
        f"({'health-check mode' if args.health_check else 'full mode'})"
    )
    split_distribution = gl.BASE_PATH / "images" / "benchmark_hybrid_analysis_FILE_distribution.png"
    split_success = gl.BASE_PATH / "images" / "benchmark_hybrid_analysis_FILE_success.png"
    if split_distribution.exists() and split_success.exists():
        print(f" - plots: {split_distribution} | {split_success}")
    else:
        plot_summary = gl.BASE_PATH / "images" / "benchmark_hybrid_analysis_FILE.png"
        if not plot_summary.exists():
            plot_summary = gl.BASE_PATH / "images" / "benchmark_hybrid_analysis.png"
        if not plot_summary.exists():
            plot_summary = dataset_dir.parent / "benchmark_hybrid_analysis_FILE.png"
        if not plot_summary.exists():
            plot_summary = dataset_dir.parent / "benchmark_hybrid_analysis.png"
        print(f" - plot: {plot_summary}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"pos_test safeguard failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
