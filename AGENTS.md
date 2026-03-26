# AGENTS.md — Repository Onboarding Guide

This file is a practical guide for automated coding agents and new contributors.
It captures the operational knowledge needed to work safely in this repository.

## 1) Mission of this repository

This project evaluates fault-localization (FL) techniques for Dafny mutants using EXAM score metrics.

Core flow:
1. Read dataset (`original/` + `killed/`)
2. Run FL techniques
3. Compute EXAM metrics
4. Cache predictions/results
5. Optionally generate plots and statistical comparisons

## 2) High-signal entry points

- `src/run_1_model.py`: run one technique on one dataset
- `src/run_all_models.py`: run all techniques + summarize
- `src/run_repo_health_check.py`: complete repository health check (type check + tests + safeguard)
- `src/run_pos_test_guard.py`: integration safeguard pipeline (preferred integration validation)
- `src/fl_eval/metrics/scoring.py`: EXAM computation + cache serialization
- `src/fl_eval/util/run_external_cmd.py`: external command execution + last-run metadata capture
- `src/analysis/data_analysis.py`: tables, plots, method comparison
- `src/config.py`: centralized paths + limits configuration
- `src/logging_config.py`: centralized logging setup

## 3) Canonical validation commands

### Unit tests

```bash
pytest -q src/tests
```

### Type checking (Pylance-equivalent)

```bash
pyright src
```

### Integration safeguard (preferred integration check)

```bash
python src/run_pos_test_guard.py --dataset-tar datasets/pos_test.tar.gz --clean-cache
```

### Complete repository health check (recommended)

```bash
python src/run_repo_health_check.py --clean-cache
```

## 4) Configuration knobs (environment variables)

- `FL_MAX_RAM_GB` (default: `24`)
- `FL_MAX_TIME_SECONDS` (default: `60`)
- `FL_VERBOSE` (`1` to print full config)
- `FL_LOG_LEVEL` (`DEBUG|INFO|WARNING|ERROR`, default `INFO`)
- `FL_LOG_FILE` (optional file path)

## 5) Cache format

Cache location: `run_artifacts/cached_results/<dataset_name>/<technique>/<mutant>.json`

All caches are organized by dataset name to allow independent cache management per dataset.

Current schema (v2) stores:
- `schema_version`: 2
- `predictions`: list of line numbers ranked by suspiciousness
- `execution_metadata`:
  - `timestamp_utc`: UTC timestamp of execution
  - `command`: command executed
  - `status`: execution status (OK, TIMEOUT, ERROR, etc.)
  - `return_code`: process return code
  - `stdout`: standard output
  - `stderr`: standard error

Important serialization note:
- metadata may include non-JSON-native values (e.g., `Path`).
- cache writing uses JSON serialization tolerant conversion (`default=str`).
- Only schema v2 format is supported (strict validation, no backward compatibility).

## 6) Logging conventions

- Use `from logging_config import get_logger`
- Create module logger: `logger = get_logger(__name__)`
- Prefer:
  - `logger.debug(...)` for diagnostics
  - `logger.info(...)` for normal progress
  - `logger.warning(...)` for recoverable issues
  - `logger.error(...)` for failures/skips

## 7) Dataset assumptions

Expected structure:
- `<dataset>/original/*.dfy`
- `<dataset>/killed/*.dfy`
- `<dataset>/killed/*.txt` (diff files)

Mutant/original pairing failures should be handled gracefully (skip with logs).

## 7b) Dataset Validation

The pipeline validates dataset structure and consistency at the start of each technique evaluation:
- Checks directory structure (original/, killed/ exist and contain .dfy files)
- Validates file pairings (diff files ↔ mutants)
- Checks original file associations
- Reports detailed diagnostics for data quality issues

**Important:** Validation errors are **non-blocking**. They are logged as errors but do not prevent
evaluation. This allows partial processing of datasets with minor structural issues. Individual
mutations handle their own robustness during processing.

Validation runs once per technique in `_setup_evaluation()` before mutation processing begins.

## 8) Common pitfalls (recently observed)

1. **Docker permissions for tests**
   - Avoid writing temp files in working directory during tests.
   - Use `tempfile.TemporaryDirectory()`.

2. **JSON cache serialization crashes**
   - If metadata includes `Path`, plain `json.dump(...)` fails.
   - Ensure tolerant serialization.

3. **Matplotlib deprecation noise**
   - Use `orientation='vertical'` instead of `vert=True` in `boxplot`.

4. **`fl_eval.util.globals` is deprecated**
   - Use `src/config.py` (`import config as gl`).

## 9) Suggested change workflow for agents

1. Read target module + tests first
2. Make smallest safe patch
3. Run `pyright src`
4. Run `pytest -q src/tests`
5. If touching pipeline behavior, run `run_pos_test_guard.py` (or `run_repo_health_check.py`)
6. Update docs when changing runtime behavior
