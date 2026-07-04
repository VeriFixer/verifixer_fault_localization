from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluators.eval_model_common import get_techniques_for_paper_only, prepare_dataset_cache
from evaluators.eval_common import parse_common_runner_args
from evaluators.eval_models import eval_models_for_techniques


def main() -> int:
    args = parse_common_runner_args(
        "RQ1 runner: execute paper technique subset with optional paper aliases."
    )
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    eval_models_for_techniques(
        args.data_path,
        get_techniques_for_paper_only(),
        sequential=args.sequential,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
