import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runners.run_model_common import get_techniques_for_llm_only, prepare_dataset_cache
from runners.run_common import parse_common_runner_args
from runners.run_models import ReportOptions, run_models_for_techniques


def main() -> int:
    args = parse_common_runner_args(
        "RQ3 runner: execute LLM techniques only."
    )
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    techniques = [
        "CNTM",
        "LLM",
        "LLM_ERR_MSG",
        "LLM_ERR_MSG_CNTM",
    ]

    run_models_for_techniques(
        args.data_path,
        techniques,
        sequential=args.sequential,
        report_options=ReportOptions(
            show_ascii_tables=False,
            show_latex_tables=False,
            show_compact_tables=True,
            show_complete_cases=False,
            show_images=False,
            show_statistics=False,
            show_llm_costs=False,
        ),
        reduce=args.reduce,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
