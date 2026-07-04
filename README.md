# Fault Localization for Dafny Programs

This repository evaluates fault-localization techniques for Dafny mutants using EXAM metrics.

## Artifact Evaluation Priority Guide

This README is ordered for artifact evaluators:
1. Fastest way to see the pipeline working.
2. How to replicate research-question runs using existing caches.
3. How to replicate everything from scratch.
4. Extra/reference details.

## 1) Fastest Way To See Something Working

### Prerequisites
1. Clone with submodules.
2. Pull LFS datasets.
3. Use Python environment with dependencies installed.

```shell
git clone --recurse-submodules git@github.com:VeriFixer/verifixer_fault_localization.git
cd verifixer_fault_localization
git lfs install
git lfs pull
```

### Fastest evaluator path (Docker first)

Right after cloning, the fastest way to evaluate is Docker.

If you already have the prebuilt image tar:

```bash
docker load -i dafny_research_latest.tar
docker run --rm -it -w /app dafny_research:latest bash
```

If you need to build locally:

```bash
DOCKER_BUILDKIT=1 docker build -t dafny_research:latest .
docker run --rm -it -w /app dafny_research:latest bash
```

Inside the container, run a fast smoke command:

```bash
python src/evaluators/eval_1_model.py random dataset/data/pos_test
```

For full container usage and troubleshooting, see [README_DOCKER.md](README_DOCKER.md).

### 60-second smoke run

Run one fast technique on the smallest packaged dataset:

```bash
python src/evaluators/eval_1_model.py random dataset/data/pos_test
```

Expected success signal:
1. A metrics summary is printed in terminal.
2. Cache files appear under `tmp/run_artifacts/cached_results/pos_test/random/`.

### One-command health validation

```bash
python src/integration_tests/health_check.py --clean-cache
```

This runs type checks, tests, and the safeguard benchmark.

## 2) Replicate Research Questions Using Cached Results

Use this path when cache artifacts already exist and you want deterministic, quick reruns.

### RQ1 (paper subset techniques)

```bash
python src/research_questions/rq1.py dataset/data/pos_test
```

### RQ2 (CNTM ablation)

```bash
python src/research_questions/rq2.py dataset/data/pos_test
```

### Full benchmark table/plots (cached-first behavior)

```bash
python src/evaluators/eval_all_models_raw_name.py dataset/data/pos_test
```

Expected outputs:
1. Terminal summary tables (file scope and method scope).
2. Plot files in `tmp/run_artifacts/images/`.
3. Cache reused from `tmp/run_artifacts/cached_results/` when present.
4. Per-mutant trace+summary artifacts in `tmp/run_artifacts/pretty_outputs/<dataset>/<technique>/`.

### Query mutants by EXAM threshold

To list mutants with EXAM above a threshold (default output is filenames only):

```bash
python src/analysis/query_exam_results.py \
	--dataset dataset/data/pos_test \
	--techniques CNTM \
	--scope file \
	--op ">" \
	--value 0.20
```

Optional output formats:

```bash
python src/analysis/query_exam_results.py \
	--dataset dataset/data/pos_test \
	--techniques CNTM,CNTS \
	--scope method \
	--op ">=" \
	--value 0.30 \
	--output json
```

## 3) Replicate Everything From Scratch

Use this path for full clean reproducibility.

### Step A: Remove old artifacts and caches

```bash
rm -rf tmp/run_artifacts/cached_results/*
rm -rf tmp/run_artifacts/images/*
```

### Step b: Run full benchmark from clean state

```bash
python src/evaluators/eval_all_models_raw_name.py dataset/data/pos_test --clean-cache
```

### Step C: Validate complete repository pipeline

```bash
python src/integration_tests/health_check.py --clean-cache
```

## 4) Additional Reference

### Repository layout highlights

1. `src/evaluators/` contains benchmark entry points.
2. `src/safeguards/` contains safeguard/integration benchmark checks.
3. `src/integration_tests/` contains repository health-check orchestration.
4. `external/` contains moved submodules:
5. `external/core/dafny`
6. `external/mutation/mutdafny`
7. `external/bench/dafnybench`
8. `external/tests_gen/spec-test-generator`
9. `external/tests_gen/dafny-test-gen`
10. `external/tools/dafny-autofix`

### Dataset shape

Expected dataset format:

```text
<dataset>/
	original/
	killed/
```

Example dataset: `dataset/data/pos_test` (from `dataset/data/pos_test.tar.gz`).

### Techniques (internal names)

1. `random`
2. `counterBase`
3. `counterExampleIf`
4. `counterExampleIfReassume`
5. `empty`
6. `autofixDefault`
7. `autofixSimplified`
8. `llm_without_api`
9. `llm_real`
10. `LLM_ERR_MSG`
11. `LLM_ERR_MSG_CNTM`

### Useful commands

Run one example:

```bash
python src/evaluators/eval_1_model_1_example.py <technique> <dfy_file>
```

Run a real LLM with Qwen via OpenRouter:

```bash
export OPENROUTER_API_KEY="<your-openrouter-api-key>" 
LLM_REAL_MODEL_NAME=qwen3-coder-next python src/evaluators/eval_1_model_1_example.py LLM_ERR_MSG_CNTM dataset/data/pos_test/killed/abs__161-188_CBE.dfy
```

The technique name goes before the Dafny file path. This form does not require exporting
the variables into your shell session. You can replace `LLM_ERR_MSG_CNTM` with `LLM`,
`LLM_NO_API`, or `LLM_ERR_MSG` depending on which LLM strategy you want to run.

Run tests and type-checking:

```bash
pytest -q src/tests
pyright src
```

For detailed operational notes, see [AGENTS.md](AGENTS.md) and [README_DOCKER.md](README_DOCKER.md).