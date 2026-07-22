import argparse
import os
from pathlib import Path

from run_1_model_1_example import compute_one_example
from fl_eval.reporting.run_one_example_output import print_section
from fl_eval.util.terminal_colors import Color, colored, separator
from logging_config import get_logger

logger = get_logger(__name__)


MIN_LINES_TO_EXPLORE = 5
MIN_STATES_TO_EXPLORE = 10
MIN_PERCENTAGE_TO_EXPLORE = 15

def compute_intersection(
    cntm_ranking: list[int],
    min_lines_to_explore: int,
    min_states_to_explore: int
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    snapshots = []
    with open('snapshots-suspiciousness-score.csv', 'r') as file:
        for line in file:
            snapshot_str = line[line.index('(')+1:line.rindex(')')]
            elements = snapshot_str.split(", ")
            snapshot = (elements[0].strip("'\""), elements[2].strip("'\""), elements[3].strip("'\""))
            score = line[line.index(')'):].split(",")[1]
            snapshots.append((snapshot, score))

    relevant_states = []
    additional_states = []

    exam_num_lines = round(len(cntm_ranking) * 15 / 100)
    base_num_lines = max(exam_num_lines, min_lines_to_explore)
    new_relevant_states, new_additional_states = get_suspicious_lines_snapshots(cntm_ranking, snapshots, 0, base_num_lines, min_states_to_explore)
    relevant_states += new_relevant_states
    additional_states += new_additional_states

    new_relevant_states, new_additional_states = get_top_suspicious_snapshots(snapshots, min_states_to_explore, relevant_states)
    relevant_states += new_relevant_states
    additional_states += new_additional_states

    new_relevant_states, new_additional_states = get_suspicious_lines_snapshots(cntm_ranking, snapshots, base_num_lines, len(cntm_ranking), min_states_to_explore)
    relevant_states += new_relevant_states
    additional_states += new_additional_states

    return relevant_states, additional_states


def get_suspicious_lines_snapshots(cntm_ranking, snapshots, start_line, end_line, min_states_to_explore):
    relevant_states = []
    additional_states = []

    for i in range(start_line, end_line):
        if i > len(cntm_ranking) - 1:
            break
        line = cntm_ranking[i]
        line_states = list(filter(lambda s: s[0][0] == str(line), snapshots))
        base_num_states = min(min_states_to_explore, len(line_states))
        score = -1
        for j in range(base_num_states):
            (relevant_states if start_line == 0 else additional_states).append(line_states[j][0])
            score = line_states[j][1]
        for j in range(base_num_states, len(line_states)):
            if line_states[j][1] != score:
                break
            additional_states.append(line_states[j][0])

    return relevant_states, additional_states


def get_top_suspicious_snapshots(snapshots, min_states_to_explore, relevant_states):
    relevant_states = []
    additional_states = []

    line = -1
    score = -1
    for snapshot in snapshots[:min_states_to_explore]:
        if not snapshot in relevant_states:
            relevant_states.append(snapshot[0])
            line = snapshot[0][0]
            score = snapshot[1]
    for snapshot in snapshots[min_states_to_explore:]:
        if snapshot[0][0] != line or snapshot[1] != score:
            break
        additional_states.append(snapshot[0])

    return relevant_states, additional_states


if __name__ == "__main__":
    USAGE_EXAMPLE = """
How to use:
  Run the script from the project root directory. Evaluate one faulty program.
    $ python src/run_cntm_snap_intersection.py dataset/data/pos_test/killed/foo.dfy
    $ python src/run_cntm_snap_intersection.py dataset/data/pos_test/killed/foo.dfy --min_lines_to_explore 3 --min_states_to_explore 3
"""

    parser = argparse.ArgumentParser(
        description="Run CNTM/SNAP fault localization intersection on a faulty program and print a report.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=USAGE_EXAMPLE,
    )

    parser.add_argument(
        "dfy_path",
        type=Path,
        help="The path to the file containing the dfy code (it will extract paths to killed, original folder from there).",
    )

    parser.add_argument(
        "--min_lines_to_explore",
        type=int,
        default=MIN_LINES_TO_EXPLORE,
        help=f"Minimum number of ranked lines to explore (default: {5}).",
    )
 
    parser.add_argument(
        "--min_states_to_explore",
        type=int,
        default=MIN_STATES_TO_EXPLORE,
        help=f"Minimum number of states to explore per line (default: {10}).",
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
            if not os.path.exists('snapshots-suspiciousness-score.csv'):
                compute_one_example(
                    "SNAP",
                    args.dfy_path,
                    enable_pretty_output=True,
                )
            main_intersection, additional_intersection = compute_intersection(
                cntm_ranking, 
                args.min_lines_to_explore, 
                args.min_states_to_explore
            )

            print_section("RESULT")
            print(f"{colored('Predictions', Color.BOLD):24}: {main_intersection}")
            print_section("")
            print(f"{colored('Additional Predictions', Color.BOLD):24}: {additional_intersection}")


        except Exception as e:
            logger.error("Single-file fault localization failed: %s", e)
            print(f"Fault localization failed: {e}")