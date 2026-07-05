import argparse
from pathlib import Path

from fl_eval.core.abstract import FLTechnique
from runners.run_model_common import (
    TECHNIQUE_MAP,
    execute_single_mutation,
)
from fl_eval.reporting.run_one_example_output import print_section
from fl_eval.util.terminal_colors import Color, colored, separator
from logging_config import get_logger

logger = get_logger(__name__)


def compute_one_example(
    flt_name: str,
    dfy_path: Path,
    enable_pretty_output: bool = False,
) -> tuple[FLTechnique, list[int]]:
    single_output = execute_single_mutation(
        flt_name,
        dfy_path,
    )
    if single_output is None:
        raise RuntimeError("Evaluation failed: could not compute single-mutation metrics.")

    return single_output


if __name__ == "__main__":
    USAGE_EXAMPLE = """
How to use:
  Run the script from the project root directory.

    Example 1: Evaluate one mutant with a non-LLM technique
        $ python src/eval_1_model_1_example.py RANDFILE dataset/data/pos_test/killed/foo__mut1.dfy

    Example 2: Evaluate one mutant with LLM (interactive, no API calls for debugging)
        $ python src/eval_1_model_1_example.py LLM_NO_API dataset/data/pos_test/killed/foo__mut1.dfy

    Example 3: Evaluate one mutant with LLM (default cost_stub_all_lines_ranked)
        $ python src/eval_1_model_1_example.py LLM dataset/data/pos_test/killed/foo__mut1.dfy

    Example 4: Evaluate one mutant with a specific LLM model (requires LLM_REAL_MODEL_NAME env var)
        $ LLM_REAL_MODEL_NAME=qwen3-coder-480b python src/eval_1_model_1_example.py LLM dataset/data/pos_test/killed/foo__mut1.dfy
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
    
    print("\n" + separator("="))
    print(colored("SINGLE FILE FAULT LOCALIZATION", Color.HEADER + Color.BOLD))
    print(separator("="))
    print_section("INPUT")
    print(f"{colored('Technique', Color.BOLD):24}: {args.technique_name}")
    print(f"{colored('Program', Color.BOLD):24}: {args.dfy_path}")
    print(separator("="))

    if not args.dfy_path.exists():
        print(f"Data path not found: {args.dfy_path}")
        parser.print_help()
    else:
        try:
            _, ranking = compute_one_example(
                args.technique_name,
                args.dfy_path,
                enable_pretty_output=True,
            )
            print_section("RESULT")
            print(f"{colored('Predictions', Color.BOLD):24}: {ranking}")

        except Exception as e:
            logger.error("Single-file fault localization failed: %s", e)
            print(f"Fault localization failed: {e}")
