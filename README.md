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
docker load -i dafny_research_latest.tar.gz
docker run --rm -it -w /app dafny_research:latest bash
```

If you need to build locally:

```bash
DOCKER_BUILDKIT=1 docker build -t dafny_research:latest .
docker run --rm -it -w /app dafny_research:latest bash
```

To save the built image as a portable tar.gz (for sharing / VM preloading):

```bash
docker save dafny_research:latest | gzip > dafny_research_latest.tar.gz
```

Inside the container, first extract the compressed datasets and caches:

```bash
bash setup_data.sh
```

Then run a fast smoke command:

5 minutes expected time
```bash
python src/runners/run_1_model.py RAND dataset/data/pos_test
```

Expected a result simmilar to this (note actual values may change as this is the RAND strategy)
```text
2026-07-14 18:02:32] [INFO    ] [runners.run_model_common] - Using cached results if any at /app/tmp/run_artifacts/cached_results/pos_test
[2026-07-14 18:02:32] [INFO    ] [__main__] - Model log file enabled: /app/tmp/run_artifacts/models_log/RAND.log
Get metrics for RAND (Active Cores:16): 100%|█| 21/21 [00:24<00
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - 
============================================================================
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] -                              EVALUATION SUMMARY                             
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - ============================================================================
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Technique                             : RAND
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Evaluated Mutations                   : 21
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - ----------------------------------------------------------------------------
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - FILE-SCOPE METRICS
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Avg EXAM (All)                        : 0.231048
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Avg EXAM (Found Only)                 : 0.231048
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Avg EXAM (Pred != Empty)              : 0.231048
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Fault Found (%)                       : 100.000000
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Empty Predictions Rate                : 0.000000
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Top-1 Success (%)                     : 14.285714
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Top-3 Success (%)                     : 33.333333
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Top-5 Success (%)                     : 47.619048
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - ----------------------------------------------------------------------------
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - METHOD-SCOPE METRICS
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Evaluated Methods                     : 21
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Avg EXAM (All)                        : 0.450306
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Avg EXAM (Found Only)                 : 0.450306
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Avg EXAM (Pred != Empty)              : 0.450306
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Fault Found (%)                       : 100.000000
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Empty Predictions Rate                : 0.000000
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Top-1 Success (%)                     : 14.285714
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Top-3 Success (%)                     : 33.333333
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - Top-5 Success (%)                     : 47.619048
[2026-07-14 18:02:56] [INFO    ] [runners.run_model_common] - ============================================================================
```

For full container usage and troubleshooting, see [README_DOCKER.md](README_DOCKER.md).

# 2) Replicate Research Questions Using Cached Results

Use this path when cache artifacts already exist and you want deterministic, quick reruns.


### RQ1 (State vs Path)

Prints compact tables for both all cases and complete cases only.

```bash
python src/research_questions/rq1.py dataset/data/sample_original_can_run --reduce
```

### RQ2 (Ranking Ablation Study)

```bash
python src/research_questions/rq2.py dataset/data/sample_original_can_run --reduce
```

### RQ3 (Path Diversity)

```bash
python src/research_questions/rq3.py dataset/data/sample_original_can_run --reduce
```

### RQ4 (LLM Baseline Comparison)

```bash
python src/research_questions/rq4.py dataset/data/sample_original_can_run --reduce
```

### Images Generation 

```bash
python src/analysis/image.py dataset/data/sample_original_can_run --reduce
```

### Statical test in annex 

```bash
python src/analysis/stats.py dataset/data/sample_original_can_run --reduce
```

## 3) Replicate Everything From Scratch
This section walks through removing cache artifacts to see how everything can be reproduced from scratch. Note that LLM techniques (due to API costs) and SNAP (due to long running times) are not fully reproducible end-to-end within a short session; steps C and D show how to validate them on a single example instead.

### Step A: Remove the cached results for a fast technique such as CNTB/CNTS/CNTM
```bash
rm -rf tmp/run_artifacts/cached_results/sample_original_can_run/CNTB
rm -rf tmp/run_artifacts/cached_results/sample_original_can_run/CNTS
rm -rf tmp/run_artifacts/cached_results/sample_original_can_run/CNTM
```

### Step B: Run the full benchmark (missing/removed caches are recomputed individually; anything still cached is reused)
```bash
python src/runners/run_all_models_raw_name.py dataset/data/sample_original_can_run --clean-cache
```

### Step C: Due to time limitations, full from-scratch reproduction is only recommended for the CNT variants. For SNAP, validate on a single example instead:

```bash
python src/runners/run_1_model_1_example.py SNAP \
   dataset/data/sample_original_can_run/killed/se2011_tmp_tmp71eb82zt_ass1_ex4__312-312_EVR_int.dfy
```

`run_1_model_1_example.py` has no separate `--verbose`/`--no-cache` flags because that behavior is always on: it deletes any existing cache entry for that mutant+technique before running (so it never reuses a stale cached prediction), and always prints the full verbose trace/report (technique trace, EXAM summary, saved JSON artifact path). There is nothing extra to pass to get fresh, verbose output.

The full-dataset SNAP run uses the same underlying script per mutant, just launched in parallel across all mutants (see `src/runners/run_1_model.py`).

### Step D: For LLM we do not provide an API key, but running on a single example would look like this:

```bash
export OPENROUTER_API_KEY="<your-openrouter-api-key>" 
LLM_REAL_MODEL_NAME=qwen3-coder-next python src/runners/run_1_model_1_example.py LLM_ERR_MSG_CNTM dataset/data/pos_test/killed/abs__161-188_CBE.dfy
```

### Step E: Dataset reproducibility (building a new mutation dataset from scratch)
Note the intention for this section is nor for the reviewer to recreate the dataset this could take some days but instead to see the scripts and steps that will be needed. So we would only recommend in seing the commands and maybe try some but do not wait for the end (it can take multiple hours or days.)

The dataset under `dataset/data/` is not handwritten; it is generated by a pipeline of scripts in `dataset/scripts/`. Building a new dataset (or regenerating the existing one) has four stages:

**Stage 1 — Generate mutants with MutDafny**

Runs MutDafny on every program in a source directory (default: the DafnyBench submodule) and buckets each mutant as `alive`, `timed-out`, or `killed` depending on whether it still verifies:
```bash
# Default input: external/bench/dafnybench/DafnyBench/dataset/ground_truth
bash dataset/scripts/generate_mutdafny_datset.sh

# Or point it at your own directory of .dfy programs:
bash dataset/scripts/generate_mutdafny_datset.sh /path/to/your/dfy_programs
```
This step is computationally expensive (hours for the full DafnyBench corpus); `MAX_JOBS` controls parallelism (defaults to `nproc`). Stop when you need

**Stage 2 — Filter to verifiable originals and generate diffs**

Keep only originals that Dafny can verify (plus their corresponding mutants):
```bash
bash dataset/scripts/get_dataset_where_postproceeded_can_run.sh \
  <full_mutant_dataset_dir> \
  <filtered_output_dir>
```
Then generate the `.txt` diff files (ground truth used by the FL techniques):
```bash
bash dataset/scripts/get_diffs_from_original_for_postproceeded_can_run.sh <filtered_output_dir>
```

**Stage 3 — Sample a subset**

For a smaller, faster-to-run dataset, randomly sample N mutants from the filtered pool into a new `original/`+`killed/` directory pair:
```bash
# Default input: dataset/data/dafnybench_original_can_run, output: dataset/data/sampled_<N>
bash dataset/scripts/sample_dataset.sh 500

# Explicit:
bash dataset/scripts/sample_dataset.sh 500 \
  dataset/data/dafnybench_original_can_run \
  dataset/data/sampled_500
```
Each mutant is picked at random (no fixed seed), copying its `.dfy`, matching `.txt` diff, and (if present) `.test.dfy` from `killed/`, plus its corresponding `original/*.dfy`.

**Important:** because sampling is random, running this script again — even against the same input — will pick a *different* subset of mutants each time. The exact dataset shipped at `dataset/data/sample_original_can_run/` (and its tarball) cannot be regenerated with this script; it is provided pre-built precisely so reviewers can reproduce results on that specific sample. Use this script to understand/inspect the sampling process, not to recreate that exact dataset.

**Stage 4 — Generate tests (required only for the SNAP technique)**

SNAP needs a `.test.dfy` file per mutant (contract-based tests). Generate them with DafnyTestGen:
```bash
bash dataset/scripts/get_dataset_where_dafnyTestGen_can_be_generated.sh \
  <input_dataset_dir> \
  <output_dataset_dir>
```

Once a new dataset directory has `original/` and `killed/` populated (and optionally `.test.dfy` files for SNAP), it can be passed as `data_path` to any of the runners or RQ scripts described above.

### What's in `dataset/data/` (pre-built intermediary states)

To avoid forcing reviewers to run the full (multi-hour) pipeline above, each stage's output is
also shipped as a tarball under `dataset/data/`. Extract any of them with
`tar xzf dataset/data/<name>.tar.gz -C dataset/data/<name>`:

- `dafnybench_all_mutants.tar.gz` — Output of Stage 1: all ~69K mutants generated by MutDafny
  from the full DafnyBench corpus, bucketed into `original/` + `killed/` (only `killed` mutants,
  i.e. those that fail verification, are kept as usable faults).
- `dafnybench_original_can_run.tar.gz` — Output of Stage 2: the subset of the above where the
  *original* program verifies cleanly with Dafny, plus its corresponding mutants and `.txt` diff
  (ground truth) files.
- `sample_original_can_run.tar.gz` — Output of Stage 3: the exact 500-mutant random sample used
  to produce the paper's results (`dataset/data/sample_original_can_run/`, already extracted in
  the repo). As noted above, this specific sample cannot be regenerated — it is shipped as-is.
- `dafnytestgen_tests_can_run.tar.gz` — Output of Stage 4: the sampled dataset with `.test.dfy`
  contract-based tests generated by DafnyTestGen, used by the SNAP technique.
- `pos_test.tar.gz` — A small dataset used by the integration safeguard
  (`src/safeguards/pos_test_guard.py`) and quick-start examples; not part of the main
  mutant-generation pipeline.
- `cached_results.tar.gz` — Pre-computed FL predictions/EXAM cache
  (`tmp/run_artifacts/cached_results/` layout) for the shipped datasets, so runners/RQ scripts
  can reproduce tables and plots without recomputing every technique from scratch.


# 5. Adding a New FL Strategy

To add a new fault localization technique:

1. Create a new class that extends `FLTechnique` (in `src/fl_eval/core/abstract.py`):

```python
from fl_eval.core.abstract import FLTechnique
from pathlib import Path

class MyNewRanker(FLTechnique):
    def get_fault_localization(self, file: Path) -> list[int]:
        # Return a list of line numbers ranked by suspiciousness (most suspicious first)
        # Return [] if no predictions can be made
        return [42, 17, 8]
```

2. Register it in `src/runners/run_model_common.py` by adding an entry to `TECHNIQUE_CONFIG`:

```python
"MY_NEW": TechniqueConfig(MyNewRanker, run_on_all_models=True),
```

3. Run it:

```bash
python src/runners/run_1_model.py MY_NEW dataset/data/sample_original_can_run
```

Or on a single mutant with rich output:

```bash
python src/runners/run_1_model_1_example.py MY_NEW \
  dataset/data/sample_original_can_run/killed/Clover_avg__90_AOR_Sub.dfy
```

The framework handles caching, EXAM computation, method-scope scoring, and reporting automatically.



### Repository layout highlights

```
.
├── src/                         # All Python source code
│   ├── runners/                 # Benchmark entry points (run one/many techniques on a dataset)
│   ├── fl_eval/                 # Core fault-localization library
│   │   ├── strategies/          #   FL technique implementations (RAND, CNT*, SNAP, LLM, …)
│   │   ├── metrics/             #   EXAM score computation and cache serialization
│   │   ├── execution/           #   External-command execution (Dafny, test runners)
│   │   ├── tracing/             #   Execution-path tracing utilities
│   │   ├── validation/          #   Dataset structure validation
│   │   ├── llm/                 #   LLM-based technique integration (OpenRouter)
│   │   ├── reporting/           #   Result formatting and output
│   │   ├── core/                #   Shared domain types and helpers
│   │   └── util/                #   General-purpose utilities
│   ├── research_questions/      # Scripts that produce paper tables/plots per RQ (rq1–rq4)
│   ├── analysis/                # Statistical tests, image generation, data summaries
│   ├── safeguards/              # Integration safeguard (pos_test_guard.py)
│   ├── integration_tests/       # Full repo health-check orchestration
│   ├── tests/                   # Unit tests (pytest)
│   ├── config.py                # Centralized paths and resource-limit configuration
│   └── logging_config.py        # Centralized logging setup
│
├── dataset/
│   ├── data/                    # Pre-built datasets and tarballs (LFS-tracked)
│   └── scripts/                 # Dataset generation pipeline (mutate → filter → sample → gen tests)
│
├── external/                    # Git submodules (third-party tools)
│   ├── core/dafny               #   Dafny verifier binary/source
│   ├── mutation/mutdafny        #   MutDafny mutation engine
│   ├── bench/dafnybench         #   DafnyBench corpus of Dafny programs
│   ├── tests_gen/spec-test-generator  # Spec-based test generator
│   ├── tests_gen/dafny-test-gen       # DafnyTestGen (contract-based test generation)
│   └── tools/dafny-autofix      #   Dafny autofix tool
│
├── tmp/run_artifacts/           # Runtime outputs (caches, logs) — git-ignored
├── Dockerfile                   # Reproducible container with Dafny + Python deps
└── AGENTS.md                    # Onboarding guide for agents/contributors
```
