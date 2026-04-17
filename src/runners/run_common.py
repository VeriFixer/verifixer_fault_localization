import argparse
from pathlib import Path

from runners.run_model_common import add_run_control_args


def build_common_runner_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "data_path",
        type=Path,
        help="Path to dataset directory (containing 'killed' and 'original' folders).",
    )
    add_run_control_args(parser)
    parser.add_argument(
        "--use-paper-names",
        action="store_true",
        help="Use publication aliases in tables/plots.",
    )
    return parser


def parse_common_runner_args(description: str) -> argparse.Namespace:
    return build_common_runner_parser(description).parse_args()
