# Fault Localization for Dafny Programs

This repository evaluates **fault localization techniques for Dafny programs** using the **EXAM score** metric on mutated Dafny datasets.

---

## Quick Start

### With Docker (recommended)

See [README_DOCKER.md](README_DOCKER.md) for complete setup.

### Clone with Submodules

```shell
git clone --recurse-submodules git@github.com:VeriFixer/verifixer_fault_localization.git
cd verifixer_fault_localization
./scripts/install-git-hooks.sh
```

### Pull Large Dataset Files (Git LFS)

Large dataset files are stored using **Git LFS**. To download them:

```shell
git lfs install
git lfs pull
```

> **Note:** If you skip this step, Git will store LFS pointers instead of actual files. The repository will still work, but you may need to manually regenerate datasets or download them separately.

### Run Evaluation

```bash
# Single technique on dataset
python src/run_1_model.py random datasets/pos_test

# All techniques
python src/run_all_models.py datasets/pos_test

# Health check (type check + tests + safeguard)
python src/run_repo_health_check.py --clean-cache
```

---

## Dataset Structure

Expected format:
```
<dataset>/
├── original/     # Passing Dafny programs
└── killed/       # Mutated versions with failing assertions
```

Example: `datasets/pos_test/` (extracted from `datasets/pos_test.tar.gz`)

---

## Available Techniques

### Standard Techniques
- `random` — randomly ranks all lines
- `counterBase` — uses Dafny counterexample output
- `counterExampleIf` — extends counterexample parsing to include `if` decision points
- `counterExampleIfReassume` — adds extra paths by assuming false on branches
- `empty` — baseline returning no predictions
- `autofixDefault`, `autofixSimplified` — AutoFix-based ranking

### LLM-Based Techniques

#### `llm_without_api` (interactive, no API calls)
Useful for debugging the complete pipeline without external LLM calls:
```bash
python src/run_1_model.py llm_without_api datasets/pos_test
```

#### `llm_real` (pluggable LLM model via environment variable)
Default uses stub mode (`cost_stub_all_lines_ranked`):
```bash
python src/run_1_model.py llm_real datasets/pos_test
```

Swap backing model via `LLM_REAL_MODEL_NAME`:
```bash
LLM_REAL_MODEL_NAME=qwen3-coder-next python src/run_1_model.py llm_real datasets/pos_test
```

Currently supported models:
- `cost_stub_all_lines_ranked` — stub mode for testing (no API calls)
- `without_api` — interactive debugging mode
- `qwen3-coder-next` — Qwen3 Coder Next model via OpenRouter

**To add new models:** Add entries to `MODEL_REGISTRY` in `src/fl_eval/llm/llm_configurations.py` with model configuration (provider, model ID, context window, costs)

---

## Commands Reference

### Run One Example
```bash
python src/run_1_model_1_example.py <technique> <dfy_file>
```
Example: `python src/run_1_model_1_example.py random datasets/pos_test/killed/absMax__2.dfy`

### Run Tests & Type Checking
```bash
pytest -q src/tests
pyright src
```

### Cache Management

Results cached in `run_artifacts/cached_results/<dataset_name>/<technique>/`

Clear cache:
```bash
rm -rf run_artifacts/cached_results/<dataset_name>
```

---

## Adding a New Technique

1. Create `src/fl_eval/strategies/my_technique.py`
2. Implement `class MyTechnique(FLTechnique)` with `get_fault_localization(file: Path) -> list[int]`
3. Register in `src/fl_eval/util/run_model_common.py` → `TECHNIQUE_CONFIG`

---

## Repository Structure

- `src/run_1_model_1_example.py` — run one technique per one particular example
- `src/run_1_model.py` — run one technique
- `src/run_all_models.py` — benchmark all techniques
- `src/fl_eval/strategies/` — technique implementations
- `datasets/` — dataset directories and tarballs
- `run_artifacts/` — cached results and outputs

For detailed onboarding, see [AGENTS.md](AGENTS.md).