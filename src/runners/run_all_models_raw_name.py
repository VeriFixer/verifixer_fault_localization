from runners.run_model_common import get_techniques_for_all_models, prepare_dataset_cache
from runners.run_common import parse_common_runner_args
from runners.run_models import run_models_for_techniques


def main() -> int:
    args = parse_common_runner_args(
        "Run all configured techniques with raw/internal names in outputs."
    )
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    run_models_for_techniques(
        args.data_path,
        get_techniques_for_all_models(),
        sequential=args.sequential,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
