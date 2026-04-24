# Reviewer Guide — Reproducing Results

Your VM has the Docker image pre-loaded. All commands run inside the container.

All project dependencies (Dafny, Z3, .NET, Daikon, Java, etc.) are defined in the `Dockerfile`.
Python dependencies are listed in `src/requirements.txt`.

## Enter the container

Your VM has the image pre-loaded. Just run:

```bash
docker run --rm -it \
  -u $(id -u):$(id -g) \
  -e PYTHONPATH=/app/src \
  -e FL_LOG_LEVEL=INFO \
  -e PYTEST_ADDOPTS='-o cache_dir=/tmp/pytest_cache' \
  -v "$(pwd)/src:/app/src:delegated" \
  -v "$(pwd)/tmp:/app/tmp:delegated" \
  -v "$(pwd)/external/tools/dafny-autofix:/app/external/tools/dafny-autofix:delegated" \
  -v "$(pwd)/external/tests_gen/dafny-test-gen:/app/external/tests_gen/dafny-test-gen:delegated" \
  -v "$(pwd)/dataset:/app/dataset:delegated" \
  -v "$(pwd)/strategies:/app/strategies:delegated" \
  -v "$(pwd)/images:/app/images:delegated" \
  -w /app \
  dafny_research:latest bash
```

### Rebuilding the Docker image from source

If you need to rebuild ( for any reason):

```bash
# From the repository root
DOCKER_BUILDKIT=1 docker build -t dafny_research:latest .
```

This builds Dafny (v4.11.0), Z3 (4.12.1), Daikon, all C# strategy binaries, DafnyTestGen, and installs Python dependencies. Takes ~15–30 min depending on hardware.

To save the image for later:

```bash
docker save -o dafny_research_latest.tar dafny_research:latest
```

## 1. Reproduce Research Questions from Cached Results

Cached predictions for all techniques are pre-shipped.
These commands recompute tables, plots, and statistical tests from cache.

The main dataset is `dataset/data/sample_original_can_run` (500 mutants from DafnyBench).

### RQ1 — State vs. Path (SNAP, CNTB, CNTS, CNTM, LLM, RAND)
(1-3 minuted)
```bash
python src/research_questions/rq1.py dataset/data/sample_original_can_run
```
Output:
- Terminal tables and latex (file-scope and method-scope EXAM, Top-k, Found/Empty rates)
  Used on paper: 
  --- Compact Results Table (All Cases) ---
  (TABLE BELLLOW THIS) -> used in V Results table II
  --- Compact Results Table (Complete Cases Only) ---
  (TABLE BELLLOW THIS) -> used in V Results table III
  --- LaTeX Table Output (Pairwise Wilcoxon, File Scope) ---
  (TABLE BELLOW THIS) -> used in Annex table VIII
  --- LaTeX Table Output (Pairwise McNemar Top-1, File Scope) ---
  (TABLE BELLOW THIS) -> used in  Annex table IX

- Plot PNGs on paper in `tmp/run_artifacts/images/`
  tmp/run_artifacts/images/benchmark_hybrid_analysis_FILE_distribution.pdf -> used in Fig. 2
  tmp/run_artifacts/images/benchmark_hybrid_analysis_FILE_success.pdf -> used in Fig. 1



### RQ2 — Ranking Ablation (CNTM variants)
(1-3 minuted)
```bash
python src/research_questions/rq2.py dataset/data/sample_original_can_run
```
Output:
- Terminal tables and latex (file-scope and method-scope EXAM, Top-k, Found/Empty rates)
Used on paper:
  --- Compact Results Table (All Cases) ---
  (TABLE BELLOW THIS with small named adaptations to fit on page) -> used on V Results table IV


### RQ3 — LLM variants (LLM, LLM_ERR_MSG, LLM_ERR_MSG_CNTM)
(1-3 minuted)
```bash
python src/research_questions/rq3.py dataset/data/sample_original_can_run
```
Output:
- Terminal tables and latex (file-scope and method-scope EXAM, Top-k, Found/Empty rates)
  --- Compact Results Table (All Cases) ---
  (TABLE BELLOW THIS with small named adaptations to fit on page) -> used on V Results table V

## 2. Re-run a Technique Without Cached Results

To verify that a technique actually runs (not just reads cache), delete its cache and re-run.

### Example: re-run CNTM from scratch
```bash
# 1. Delete CNTM cache
rm -rf tmp/run_artifacts/cached_results/sample_original_can_run/CNTM

# 2. Run only CNTM on the dataset
python src/runners/run_1_model.py CNTM dataset/data/sample_original_can_run
```

You will see CNTM invoking the verifier for each mutant and producing fresh predictions.
Once complete, the cache is repopulated and results match the pre-shipped values. (15 min of time to complete)

### General pattern for any technique

```bash
rm -rf tmp/run_artifacts/cached_results/sample_original_can_run/<TECHNIQUE_NAME>
python src/runners/run_1_model.py <TECHNIQUE_NAME> dataset/data/sample_original_can_run
```

Where `<TECHNIQUE_NAME>` is one of: `RAND`, `CNTB`, `CNTS`, `CNTM`, `SNAP`, `LLM`, etc.

### Run a single mutant with rich output

Use `run_1_model_1_example.py` — it always produces detailed trace output for one file:

```bash
python src/runners/run_1_model_1_example.py CNTM \
  dataset/data/sample_original_can_run/killed/Clover_avg__90_AOR_Sub.dfy
```

This prints the counterexample extraction, ranking, and EXAM computation step by step.

To get rich per-mutant output when running the full dataset, use `--sequential --pretty-output`:
(but this will make the program a lot slower as it will not run in parallel)
(run the following column in from a clean cache state will take hours for not being made in parallel.)

```bash
python src/runners/run_1_model.py CNTM dataset/data/sample_original_can_run \
  --sequential --pretty-output
```

---

## 3. Caveats per Technique

### LLM techniques require an OpenRouter API key

The LLM techniques (`LLM`, `LLM_ERR_MSG`, `LLM_ERR_MSG_CNTM`) call the `qwen3-coder-next` model via OpenRouter.

To run them live it is needed a OPENROUTER_API_KEY:

```bash
export OPENROUTER_API_KEY="<your-key>"
export LLM_REAL_MODEL_NAME=qwen3-coder-next
python src/runners/run_1_model.py LLM dataset/data/sample_original_can_run
```

Single-mutant example with LLM:

```bash
export OPENROUTER_API_KEY="<your-key>"
LLM_REAL_MODEL_NAME=qwen3-coder-next python src/runners/run_1_model_1_example.py LLM \
  dataset/data/sample_original_can_run/killed/Clover_avg__90_AOR_Sub.dfy
```

### SNAP (AutoFix-based) is slow — ~16 hours for full replication

SNAP requires test generation, invariant inference via Daikon, and enumeration-based snapshot scoring.
Full replication of SNAP on 500 mutants takes approximately 16 hours. We do not recommend re-running it on the full dataset.

To see SNAP in action on a single mutant with rich output:
(5-10 minutes)
```bash
python src/runners/run_1_model_1_example.py SNAP \
   /app/dataset/data/sample_original_can_run/killed/se2011_tmp_tmp71eb82zt_ass1_ex4__312-312_EVR_int.dfy
```

This shows the full SNAP pipeline (test generation, invariant inference, snapshot ranking) for one file in a few minutes. Full replication is not advised to the the long time it would require.

---

## 4. Replicate the Dataset from Scratch

The dataset pipeline has four stages. Each script in `dataset/scripts/` accepts input/output paths as arguments (defaults match the pre-shipped layout).

### Stage 1 — Generate mutants with MutDafny

Runs MutDafny on all 785 DafnyBench programs to produce ~69K mutants:

```bash
# Default: reads from external/bench/dafnybench/DafnyBench/dataset/ground_truth
bash dataset/scripts/generate_mutdafny_datset.sh

# Explicit (equivalent to default):
bash dataset/scripts/generate_mutdafny_datset.sh \
  external/bench/dafnybench/DafnyBench/dataset/ground_truth
```

The pre-generated archive is `dataset/data/dafnybench_all_mutants.tar.gz`.
To use it instead of regenerating:

```bash
mkdir -p dataset/data/dafnybench_all_mutants
tar xzf dataset/data/dafnybench_all_mutants.tar.gz -C dataset/data/dafnybench_all_mutants
```

### Stage 2 — Filter to compilable/verifiable originals

Keeps only originals that Dafny can verify, and their corresponding mutants:

```bash
# Default: input=dataset/data/dafnybench_all_mutants, output=dataset/data/dafnybench_original_can_run
bash dataset/scripts/get_dataset_where_postproceeded_can_run.sh

# Explicit (equivalent to default):
bash dataset/scripts/get_dataset_where_postproceeded_can_run.sh \
  dataset/data/dafnybench_all_mutants \
  dataset/data/dafnybench_original_can_run
```

Then generate diff files (ground truth):

```bash
# Default: dataset/data/dafnybench_original_can_run
bash dataset/scripts/get_diffs_from_original_for_postproceeded_can_run.sh

# Explicit (equivalent to default):
bash dataset/scripts/get_diffs_from_original_for_postproceeded_can_run.sh \
  dataset/data/dafnybench_original_can_run
```

### Stage 3 — Sample 500 mutants

The sampling step selects 500 mutants from the filtered pool.
The pre-sampled dataset is at `dataset/data/sample_original_can_run/`.

### Stage 4 — Generate tests (for SNAP)

Generates contract-based tests using DafnyTestGen for each mutant:

```bash
# Default: input=dataset/data/sampled_4, output=dataset/data/dafnytestgen_tests_can_run_samp4
bash dataset/scripts/get_dataset_where_dafnyTestGen_can_be_generated.sh

# Explicit (equivalent to default):
bash dataset/scripts/get_dataset_where_dafnyTestGen_can_be_generated.sh \
  dataset/data/sampled_4 \
  dataset/data/dafnytestgen_tests_can_run_samp4
```

> Stages 1–2 are computationally expensive (hours). The pre-built tarballs in `dataset/data/` contain all intermediate results so reviewers can skip to any stage.

### Replicate the full pipeline end-to-end

Once the dataset is ready (or using the pre-shipped one), run the full benchmark from scratch:

```bash
# Clean all caches
rm -rf tmp/run_artifacts/cached_results/*
rm -rf tmp/run_artifacts/images/*

# Run all techniques
python src/runners/run_all_models_raw_name.py dataset/data/sample_original_can_run --clean-cache

# Reproduce RQ tables/plots
python src/research_questions/rq1.py dataset/data/sample_original_can_run
python src/research_questions/rq2.py dataset/data/sample_original_can_run
python src/research_questions/rq3.py dataset/data/sample_original_can_run
```

---

## 5. Adding a New FL Strategy

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

---

## 6. Quick Reference

| Command | What it does | Time |
|---|---|---|
| `python src/research_questions/rq1.py ...` | RQ1 from cache | ~1 min |
| `python src/research_questions/rq2.py ...` | RQ2 from cache | ~1 min |
| `python src/research_questions/rq3.py ...` | RQ3 from cache | ~1 min |
| `python src/runners/run_all_models_raw_name.py ...` | All techniques from cache | ~2 min |
| `rm -rf .../CNTM && python src/runners/run_1_model.py CNTM ...` | Re-run CNTM fresh | ~2–4 hours |
| `python src/runners/run_1_model_1_example.py CNTM .../killed/<file>.dfy` | One mutant, rich output | ~1 min |
| `python src/runners/run_1_model.py CNTM ... --sequential --pretty-output` | Full dataset, rich output | ~4 hours |
| `python src/integration_tests/health_check.py --clean-cache` | Full repo health check | ~30 min |
