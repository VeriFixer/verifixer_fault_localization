ISSRE 2026 ARTIFACT EVALUATION README
======================================

1. TARGET CATEGORY
-------------------
Code

2. TARGET BADGE
----------------
Available, Reviewed, Reproducible

3. INFO
-------
Title: Automated Fault Localization for Verification-Aware Languages: A Study on Dafny
Submission ID: 225

Authors:
- Alvaro Silva, INESC TEC, Faculty of Engineering, University of Porto, Porto, Portugal
  alvaro.silva@fe.up.pt (ORCID: 0009-0005-2941-9942)
- Isabel Amaral, INESC TEC, Faculty of Engineering, University of Porto, Porto, Portugal
  isabel.andre.amaral@gmail.com
- Alexandra Mendes, INESC TEC, Faculty of Engineering, University of Porto, Porto, Portugal
  alexandra@archimendes.com (ORCID: 0000-0001-8060-5920)
- Joao Pascoal Faria, INESC TEC, Faculty of Engineering, University of Porto, Porto, Portugal
  jpf@fe.up.pt (ORCID: 0000-0003-3825-3954)

4. EXPECTED BEHAVIOUR
----------------------
This artifact is the full implementation used to run and evaluate fault-localization (FL)
techniques on mutated Dafny programs, as studied in the paper.

Given a dataset of Dafny mutants (each paired with its unmutated original and a ground-truth
diff), the artifact:
- runs one or more FL techniques (RAND, CNTB/CNTS/CNTM, SNAP, LLM-based variants, etc.) that
  each produce a ranked list of suspicious source lines per mutant;
- computes EXAM-score metrics (file-scope and method-scope) comparing predicted rankings
  against the ground-truth faulty line;
- aggregates results into the tables and plots reported in the paper (RQ1-RQ4, Section V and
  the Annex);
- caches predictions/results so re-runs are fast and reproducible.

Scope: the artifact covers the full pipeline end to end (dataset -> FL technique -> EXAM
metric -> aggregated tables/plots), on the 500-mutant sample of DafnyBench used in the paper.
It also includes the scripts used to build that dataset from scratch (mutation generation,
filtering, sampling, test generation), though re-running those from zero is not required to
reproduce the paper's results, since we ship the pre-built dataset and pre-computed caches.

Output: terminal tables (plain + LaTeX), PNG/PDF plots under tmp/run_artifacts/images/, and
per-mutant JSON cache/trace artifacts under tmp/run_artifacts/cached_results/ and
tmp/run_artifacts/pretty_outputs/.

5. ARTIFACT DESCRIPTION
------------------------
Repository root (see README.md "Repository layout highlights" for full detail):

- src/                    Python source (FL techniques, EXAM metric, runners, RQ scripts)
  - runners/              Entry points to run one/many techniques on a dataset
  - fl_eval/              Core FL library (strategies, metrics, execution, LLM integration)
  - research_questions/   rq1.py..rq4.py, one script per paper research question
  - analysis/             Plots, statistical tests (stats.py), data summaries
  - safeguards/           Integration safeguard (pos_test_guard.py)
  - integration_tests/    Full repo health check
  - tests/                Unit tests (pytest)
- dataset/
  - data/                 Pre-built datasets and tarballs (Git LFS), including
                          sample_original_can_run (the 500-mutant sample used in the paper)
                          and pos_test (small smoke-test dataset)
  - scripts/              Dataset generation pipeline (mutate -> filter -> sample -> gen tests)
- external/               Git submodules (Dafny, MutDafny, DafnyBench, test generators)
- tmp/run_artifacts/       Runtime outputs: caches, logs, images (git-ignored, populated on run)
- Dockerfile               Reproducible container: Dafny, Z3, .NET, Daikon, Java, Python deps
- README.md                Primary usage guide (fastest path, RQ replication, from-scratch
                            replication, adding new FL strategies)
- README_DOCKER.md          Docker build/run reference
- AGENTS.md                 Engineering conventions and validation commands
- LICENSE                   MIT license (open-source, permissive)

6. ENVIRONMENT SETUP
----------------------
Recommended: use the provided Docker image. This is the only officially supported environment
and avoids installing Dafny, Z3, .NET, Daikon and Java natively.

Minimum resources: 4 CPU cores, 8 GB RAM free for the container (default resource limits used
by the pipeline are configurable via FL_MAX_RAM_GB / FL_MAX_TIME_SECONDS, see README.md).
Disk: ~5 GB for the image plus dataset tarballs.

Load the prebuilt image (if shipped as a tar):
    docker load -i dafny_research_latest.tar
    docker run --rm -it -w /app dafny_research:latest bash

Or build it locally from the repo root (~15-30 min):
    DOCKER_BUILDKIT=1 docker build -t dafny_research:latest .
    docker run --rm -it -w /app dafny_research:latest bash

See README.md section "Fastest evaluator path (Docker first)" to know how to load Docker.

7. GETTING STARTED
--------------------
Estimated time: under 10 minutes.

Inside the container, first extract the compressed datasets and cached results:
    bash setup_data.sh

This extracts dataset/data/pos_test, dataset/data/sample_original_can_run, and
tmp/run_artifacts/ (cached_results, images, models_log) from their compressed archives.
It is idempotent — re-running it skips already-extracted directories.

Then run the smoke test on the small pos_test dataset:
    python src/runners/run_1_model.py RAND dataset/data/pos_test

Expected: a progress bar over 21 mutants (~15-25 seconds) followed by an EVALUATION SUMMARY
block reporting file-scope and method-scope EXAM, Fault Found %, Top-1/3/5 Success for the
RAND technique. Exact numeric values may vary run-to-run because RAND is non-deterministic;
successful completion with a populated summary table is the pass criterion.

Full details and sample expected output: README.md, section "1) Fastest Way To See Something
Working".

8. REPRODUCIBILITY
--------------------
The paper's main dataset is dataset/data/sample_original_can_run (500 DafnyBench mutants).
Pre-computed caches are shipped in dataset/data/cached_results.tar.gz so that RQ scripts
reproduce paper tables/plots deterministically in 1-3 minutes each, without recomputing every
technique from scratch:

    python src/research_questions/rq1.py dataset/data/sample_original_can_run --reduce
    python src/research_questions/rq2.py dataset/data/sample_original_can_run --reduce
    python src/research_questions/rq3.py dataset/data/sample_original_can_run --reduce
    python src/research_questions/rq4.py dataset/data/sample_original_can_run --reduce
    python src/analysis/image.py dataset/data/sample_original_can_run --reduce
    python src/analysis/stats.py dataset/data/sample_original_can_run --reduce

Mapping of script output to paper artifacts (tables/figures) is documented inline in
README.md, section "2) Replicate Research Questions Using Cached Results".

To verify techniques are not just reading stale cache, individual technique caches can be
deleted and recomputed (fast for CNTB/CNTS/CNTM, minutes; SNAP is slow, ~16h for the full
dataset, so we recommend the single-mutant SNAP example instead); see README.md, section
"3) Replicate Everything From Scratch" for the full from-scratch procedure, including:
- Step A/B: deleting caches and re-running the full benchmark
  (src/runners/run_all_models_raw_name.py --clean-cache)
- Step C: single-mutant SNAP validation
- Step D: single-mutant LLM validation (requires an OpenRouter API key, not provided)
- Step E: rebuilding the mutant dataset itself from DafnyBench via dataset/scripts/
  (multi-hour/day process; provided for transparency, not required or recommended for reproduction)

Note on LLM-based techniques: reproducing exact paper values requires an OPENROUTER_API_KEY
which we cannot ship for cost/security reasons; cached LLM predictions used in the paper are
included in dataset/data/cached_results.tar.gz so RQ3/RQ4 tables reproduce without a key.