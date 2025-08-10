# Copilot Instructions for gamer_regression

## Project Overview
- **GAMER**: GPU-accelerated Adaptive Mesh Refinement code for astrophysical simulations. The main code is in `src/`.
- There are two part in the workspace: the main code and the regression test code.
- Main development focus: `regression_test/` (active development, main area for contributions).

## VS Code Environment
- Dependency setup is already complete; do not modify or re-run environment setup scripts.

## Regression Testing
- Run `conda activate regression` to activate the conda environment for regression test.
- For smoke test, run `python regression_test/regression_test.py --machine=perlmutter --name 4 --type 1 -o quick_test --no-upload`
- For full test, run `python regression_test/regression_test.py --machine=perlmutter` to start the regression tests.
- Note: Since the tests structure are still in development, it is normal that all the tests failed.

## Best practices
- Run the regression test to check if your modifications works.

## Regression Test Structure

### Files
1. **`PRD_refactor_regression_test.md`**
   - Contains a Product Requirements Document (PRD) for refactoring the regression test framework.
   - Sections include objectives, current issues, proposed solutions, and deliverables.

2. **`clean_reg.sh`**
   - A shell script to clean up regression test artifacts.
   - Removes logs, comparison results, and test inputs.

3. **`regression_test.py`**
   - The main Python script for running regression tests.
   - Includes functions for logging, test execution, and result summarization.

4. **`requirements.txt`** Lists Python dependencies for the regression test framework

### Folders
1. **`run/`** Directory for running regression tests.

2. **`script/`** Contains the source code of the regression test.

3. **`tests/`** A “test” is identified by `<TestName>_<Type>`.
   - Example: `Riemann_Hydro`, `Plummer_Gravity`, `MHD_ABC_MHD`.

## Quick mental model for tests (keep this short and stable)

- A “test” is identified by `<TestName>_<Type>`.
  - Example: `Riemann_Hydro`, `Plummer_Gravity`, `MHD_ABC_MHD`.
- Discovery: the runner reads `regression_test/tests/<TestName>/configs` and expands each defined `Type` into one test key `<TestName>_<Type>`.
- Execution loop: in `regression_test.py`, the `for test in tests:` loop iterates these `<TestName>_<Type>` units.

### Run directory shape (current)
- Per test: `regression_test/run/<TestName>_<Type>/case_##/`
  - Only two levels: `<TestName>_<Type>` then `case_##`.
  - This may change later; don’t depend on deeper paths.

### Authoring tests (high level)
- Place per-problem files in `regression_test/tests/<TestName>/`:
  - `Inputs/` with baseline input files (e.g., `Input__Parameter`, `Input__TestProb`, optional `clean.sh`).
  - `configs` YAML defining one or more `Type` entries and their `cases`.
- Each `Type` contains a list of `cases`; the runner will compile and run `case_00`, `case_01`, … under the run directory above.

### What changes most vs. what’s stable
- Stable: the `<TestName>_<Type>` identity; two-level run path; per-case subfolders named `case_##`.
- Variable: specific Makefile options, MPI settings, reference sources, comparison details. See `regression_test/README.md` for the deep dive.
