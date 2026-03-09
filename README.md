# Fault Localization for Dafny Programs

This repository explores multiple strategies for **fault localization in Dafny programs**, focusing on identifying missing or incorrect assertion locations using heuristic, randomized, and model-based techniques.

---

## Getting Started

If you are **not using the datasets already included in the repository**, and you want to generate datasets such as `pos_mutation` or `pos_test`, run:

```bash
./src/generate_mutdafny_dataset.sh
./src/clean_mutdafny_datset.sh
./src/get_pos.sh  
```

these creat the diff files and create two datasets 
the complete from mutdafny will all the files under 
"datasets/dafnybench_all_mutants"
and the one where the orignial runs with the versions of the tools
"datasets/dafnybench_original_can_run"

For both of them on killed in writes the diff from the initial original file

> Skip this step if you plan to use the datasets already provided.

---

## Running a Single Model

To run a specific fault localization technique on a dataset:

```bash
cd src
python run_1_model.py [model_name] dataset_path
```

To list all available models:

```bash
python run_1_model.py
```

### Example

Run the random strategy on the full mutation dataset:

```bash
python run_1_model.py random pos_mutation
```

* `pos_mutation`: ~1800 test cases
* `pos_test`: 30 test cases

Choose the dataset based on your experimental goals.

---

## Running All Models and Generating Results

To execute **all available models** on a dataset and generate result tables and plots:

```bash
python run_all_models.py dataset_path
```

This will:

* Run every strategy on the given dataset
* Generate result tables
* Produce summary graphs with overall scores

> Currently, the best-performing strategy is `counterExampleIf`, with a mean exam score of approximately **0.08**.

---

## Caching

Results are cached across runs to avoid recomputation.

To delete cached results for a specific model:

```bash
rm -rf cached_results/{model_name}
```

---

## Creating New Models

To add a new fault localization strategy:

1. Navigate to:

   ```text
   src/fl_eval/strategies
   ```

2. Create a new strategy file implementing the `FLTechnique` class.

3. Implement the method:

   ```python
   get_fault_localization(dafny_file) -> list[int]
   ```

   This method should return a list of line numbers (ordered by importance) where faults are suspected.

### Examples

* See `random_line_of_method_that_fails.py` for a simple strategy.
* This example also demonstrates how to invoke an **external program** (e.g., a C# executable).

### External C# Strategies

If your strategy relies on a new C# executable:

* Place the corresponding project under the top-level `strategies/` directory.
* Example:

  ```text
  strategies/ReturnAtRandomAllLinesOfFailingMethod
  ```

> Docker support is planned; once available, these projects will be built automatically.