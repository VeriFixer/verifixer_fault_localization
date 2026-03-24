# Fault Localization for Dafny Programs

This repository implements and evaluates **fault localization techniques for Dafny programs**. The core evaluation framework computes the **EXAM score** for different ranking strategies, using datasets built from Dafny programs and their mutated variants.

---

## Getting the Repository

To properly set up this repository, you need to clone it with submodules and (optionally) download large dataset files via Git LFS.

### Clone with Submodules

This repository uses submodules, so you must clone it recursively:

```shell
git clone --recurse-submodules git@github.com:VeriFixer/verifixer_fault_localization.git
cd verifixer_fault_localization
```
If you already cloned without submodules, run:
```shell
git submodule update --init --recursive
```
### (Optional) Download Prebuilt Datasets with Git LFS

Some large files (e.g., prebuilt datasets) are stored using Git LFS.

First, install Git LFS:
```shell
git lfs install
```
Then pull the LFS files:
```shell
git lfs pull
```
If you skip this step, the repository will still work, but you may need to regenerate datasets manually.


## Quick Start with Docker

For the easiest setup, use the provided Docker environment. This includes Dafny, Python dependencies, and all tools pre-installed.

### Option 1: Use Pre-built Image (Recommended for Reviewers)

If you have the `dafny_research_latest.tar` image:

```bash
docker load -i dafny_research_latest.tar
docker run --rm -it -w /app dafny_research:latest bash
```

### Option 2: Build from Dockerfile

```bash
docker build -t dafny_research:latest .
docker run --rm -it -w /app dafny_research:latest bash
```

### Option 3: Run with Volume Mounts (for Development)

```bash
docker run --rm -it \
  -u $(id -u):$(id -g) \
  -v "$(pwd)/src:/app/src:delegated" \
  -v "$(pwd)/mutdafny:/app/mutdafny:delegated" \
  -v "$(pwd)/datasets:/app/datasets:delegated" \
  -w /app \
  dafny_research:latest bash
```

Once inside the container, follow the instructions below.

---

## Project Layout (Quick Overview)

- `src/` — Main Python evaluation framework.
  - `run_1_model.py` — Run one technique and compute EXAM score.
  - `run_all_models.py` — Run all implemented techniques and generate summary tables + plots.
  - `fl_eval/` — Core evaluation library (strategies, metrics, ground truth parsing, utilities).
  - `pos_mutation/` — Example dataset: contains `killed/` and `original/` subfolders.
  - `pos_test/` — Small dataset for quick experiments.
- `strategies/` — (Optional) C# helper projects used by some strategies.
- `datasets/` — Generated dataset outputs (e.g., filtered subsets).
- `mutdafny/` — Mutation tool integration.
- `dafny/` — Dafny source code and tools.

---

## Prerequisites (Non-Docker Setup)

If not using Docker:

1. **Python 3.11+** (recommended)
2. **Dafny** (for dataset generation / verification) (provided as a git submodule)
3. **.NET SDK** (for building C# strategies) (version 8)
4. Optional: **mutdafny** (if generating the full mutation dataset) (provided as a git submodule)

### Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt
```
### More installation guidelines

For the rest of all installation steps follow the Dockerfile

---

## Dataset Structure

The evaluation scripts expect a dataset directory containing **two subfolders**:

- `original/` — the original (passing) Dafny programs
- `killed/` — mutated versions of the originals that contain failing assertions

Example paths in this repo:

- `src/pos_mutation/` (larger dataset)
- `src/pos_test/` (smaller test dataset)

Each mutation entry is represented as a `.txt` diff file (`killed/*.txt`) and a corresponding `.dfy` mutant (`killed/*.dfy`).

### Generating Datasets (Optional)

If you need to generate datasets:

```bash
./src/generate_mutdafny_dataset.sh
./src/clean_mutdafny_datset.sh
./src/get_pos.sh
```

This creates datasets in `datasets/dafnybench_all_mutants` and `datasets/dafnybench_original_can_run`.

> Skip if using provided datasets.

---

## Running the Evaluation

### Run a single technique

```bash
python src/run_1_model.py <technique> <dataset_path>
```

Example:

```bash
python src/run_1_model.py random src/pos_mutation
```

### Run all implemented techniques and generate results

```bash
python src/run_all_models.py src/pos_mutation
```

This produces:

- Console summary tables (ASCII + LaTeX)
- A `benchmark_hybrid_analysis.png` plot (saved next to the dataset directory)

### Cache behavior

Results are cached in `src/cached_results/`.

To clean the cache (for a specific technique):

```bash
rm -rf src/cached_results/<technique_name>
```

---

## Available Fault Localization Techniques

The following techniques are implemented and available out-of-the-box (see `src/run_1_model.py`):

- `random` — randomly ranks all lines in the failing program.
- `randomOnFailingMethod` — randomly ranks lines from the failing method.
- `counterBase` — uses Dafny counterexample output to rank suspicious lines.
- `counterExampleIf` — extends counterexample parsing to include `if` decision points.
- `counterExampleIfReassume` — extends counterexample parsing to include `if` decision points and that gets extra counterexaples by assuming false on branches to find more paths where postconditions were failing.
- `empty` — baseline that returns no predictions.

> To see the current list at runtime, run `python src/run_1_model.py --help`.

---

## Adding a New Technique

1. Create a new Python file in `src/fl_eval/strategies/`.
2. Implement a class derived from `fl_eval.core.abstract.FLTechnique`.
3. Implement:

```python
def get_fault_localization(dafny_file: Path) -> list[int]:
    ...
```

4. Register the strategy in `src/run_1_model.py` by adding it to `TECHNIQUE_MAP`.

---

## 📌 Notes & Recommendations

- The evaluation measures **EXAM score**, which corresponds to the effort required to find the fault (lower is better).
- The pipeline expects a consistent `killed/` / `original/` pairing. Missing pairs will be skipped.
- Dataset generation scripts depend on a working `mutdafny` and Dafny installation.