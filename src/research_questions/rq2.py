from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fl_eval.util.run_model_common import get_techniques_for_cntm_ablation, prepare_dataset_cache
from run_common import parse_common_runner_args
from run_models import run_models_for_techniques


def main() -> int:
    args = parse_common_runner_args(
        "RQ2 runner: execute CNTM ablation variants only."
    )
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    run_models_for_techniques(
        args.data_path,
        get_techniques_for_cntm_ablation(),
        sequential=args.sequential,
        use_paper_names=args.use_paper_names,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
