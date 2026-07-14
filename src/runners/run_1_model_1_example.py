
import argparse
from pathlib import Path

from fl_eval.core.abstract import FLTechnique
from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from fl_eval.metrics.scoring import ExamOutput
from runners.run_model_common import (
    TECHNIQUE_MAP,
    execute_single_mutation,
)
from fl_eval.reporting.run_one_example_output import (
    clean_cache_for_run,
    print_one_example_intro,
    print_section,
    render_one_example_pretty_result,
    save_one_example_json_artifact,
)
from logging_config import get_logger

logger = get_logger(__name__)

def compute_metrics_one_example(
    flt_name: str,
    dfy_path: Path,
    enable_pretty_output: bool = False,
    reduce: bool = False,
) -> tuple[FLTechnique, ExamOutput, Path, GroundTruthAndLineLimit, Path]:
    single_output = execute_single_mutation(
        flt_name,
        dfy_path,
        to_validate_dataset=False,
        reduce=reduce,
    )
    if single_output is None:
        raise RuntimeError("Evaluation failed: could not compute single-mutation metrics.")

    fl_technique, score, context, base_path = single_output

    artifact_path = save_one_example_json_artifact(
        flt_name,
        dfy_path,
        fl_technique,
        score,
        context.diff_path,
        context.gtruth,
        base_path,
    )

    if enable_pretty_output:
        render_one_example_pretty_result(
            flt_name,
            dfy_path,
            fl_technique,
            score,
            context.diff_path,
            context.gtruth,
            base_path,
            artifact_path=artifact_path,
        )

    return fl_technique, score, context.diff_path, context.gtruth, base_path



if __name__ == "__main__":
    USAGE_EXAMPLE = """
How to use:
  Run the script from the project root directory.

    Example 1: Evaluate one mutant with a non-LLM technique
        $ python src/run_1_model_1_example.py RANDFILE dataset/data/pos_test/killed/foo__mut1.dfy

    Example 2: Evaluate one mutant with LLM (interactive, no API calls for debugging)
        $ python src/run_1_model_1_example.py LLM_NO_API dataset/data/pos_test/killed/foo__mut1.dfy

    Example 3: Evaluate one mutant with LLM (default cost_stub_all_lines_ranked)
        $ python src/run_1_model_1_example.py LLM dataset/data/pos_test/killed/foo__mut1.dfy

    Example 4: Evaluate one mutant with a specific LLM model (requires LLM_REAL_MODEL_NAME env var)
        $ LLM_REAL_MODEL_NAME=qwen3-coder-480b python src/run_1_model_1_example.py LLM dataset/data/pos_test/killed/foo__mut1.dfy
"""

    parser = argparse.ArgumentParser(
        description="Run one fault-localization technique on one mutant file and print a detailed report.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=USAGE_EXAMPLE,
    )

    parser.add_argument(
        "technique_name",
        type=str,
        choices=TECHNIQUE_MAP.keys(),
        help="The name of the Fault Localization technique to evaluate (e.g., 'random').",
    )

    parser.add_argument(
        "dfy_path",
        type=Path,
        help="The path to the file containing the dfy code (it will extract paths to killed, original folder from there).",
    )

    args = parser.parse_args()
    
    print_one_example_intro(args.technique_name, args.dfy_path)

    if not args.dfy_path.exists():
        print(f"Data path not found: {args.dfy_path}")
        parser.print_help()
    else:
        clean_cache_for_run(args.dfy_path, args.technique_name, enable_pretty_output=True)

        print_section("EXECUTION")
        try:
            _, score, _, _, _ = compute_metrics_one_example(
                args.technique_name,
                args.dfy_path,
                enable_pretty_output=True,
            )
            print("Evaluation completed")
            print(
                    f"Technique={args.technique_name} mutant={args.dfy_path.name} "
                    f"file_exam={score.file.score:.6f} method_exam={score.method.score:.6f} "
                    f"found={score.file.found}"
                )

        except Exception as e:
            logger.error("Single-file evaluation failed: %s", e)
            print(f"Evaluation failed: {e}")
