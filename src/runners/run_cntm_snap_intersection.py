import argparse
from pathlib import Path

from run_1_model_1_example import compute_one_example
from fl_eval.reporting.run_one_example_output import print_section
from fl_eval.util.terminal_colors import Color, colored, separator
from logging_config import get_logger

logger = get_logger(__name__)


MIN_LINES_TO_EXPLORE = 3
MIN_STATES_TO_EXPLORE = 3
MIN_PERCENTAGE_TO_EXPLORE = 15

def compute_intersection(
    cntm_ranking: list[int]
) -> list[tuple[str, str, str]]:
    snapshots = []
    with open('snapshots-suspiciousness-score.csv', 'r') as file:
        for line in file:
            snapshot_str = line[line.index('(')+1:line.rindex(')')]
            elements = snapshot_str.split(", ")
            snapshot = (elements[0].strip("'\""), elements[2].strip("'\""), elements[3].strip("'\""))
            snapshots.append(snapshot)

    relevant_states = []
    exam_num_lines = round(len(cntm_ranking) * 15 / 100)
    for i in range(max(exam_num_lines, MIN_LINES_TO_EXPLORE)):
        if i > len(cntm_ranking) - 1:
            break
        line = cntm_ranking[i]
        line_states = list(filter(lambda s: s[0] == str(line), snapshots))
        relevant_states += line_states[:MIN_STATES_TO_EXPLORE]
    for snapshot in snapshots[:MIN_STATES_TO_EXPLORE]:
        if not snapshot in relevant_states:
            relevant_states.append(snapshot)

    return relevant_states


if __name__ == "__main__":
    USAGE_EXAMPLE = """
How to use:
  Run the script from the project root directory. Evaluate one mutant.
    $ python src/run_cntm_snap_intersection.py dataset/data/pos_test/killed/foo__mut1.dfy
"""

    parser = argparse.ArgumentParser(
        description="Run CNTM/SNAP fault localization intersection one mutant file and print a detailed report.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=USAGE_EXAMPLE,
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
    print(f"{colored('Technique', Color.BOLD):24}: CNTM/SNAP")
    print(f"{colored('Program', Color.BOLD):24}: {args.dfy_path}")
    print(separator("="))

    if not args.dfy_path.exists():
        print(f"Data path not found: {args.dfy_path}")
        parser.print_help()
    else:
        try:
            _, cntm_ranking = compute_one_example(
                "CNTM",
                args.dfy_path,
                enable_pretty_output=True,
            )
            compute_one_example(
                "SNAP",
                args.dfy_path,
                enable_pretty_output=True,
            )
            intersection = compute_intersection(cntm_ranking)

            print_section("RESULT")
            print(f"{colored('Predictions', Color.BOLD):24}: {intersection}")

        except Exception as e:
            logger.error("Single-file fault localization failed: %s", e)
            print(f"Fault localization failed: {e}")