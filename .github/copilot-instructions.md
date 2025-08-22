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
1. **`clean_reg.sh`**
   - A shell script to clean up regression test artifacts.

2. **`regression_test.py`**
   - Entry point for running regression tests.
   - Orchestrates per-case execution, reference fetching, comparison, and summary.

### Folders
1. **`run/`** Directory for running regression tests.
   - Per case: `regression_test/run/<TestName>_<Type>_c##/`
   - References are staged flat under `reference/` inside the case folder.
   - Current outputs are compared by basename against files in `reference/`.

2. **`script/`** Contains the source code of the regression test.

3. **`tests/`** Test problem definitions and configs.
- Place per-problem files in `regression_test/tests/<TestName>/`:
   - `Inputs/` with baseline input files (e.g., `Input__Parameter`, `Input__TestProb`, optional `clean.sh`).
   - `configs` YAML defining one or more `Type` entries and their `cases`.
   - Each `Type` contains a list of `cases` (e.g., `c00`, `c01`, …); the runner creates per-case run folders using the flattened ID.

## Quick mental model for tests
- Identity: execution happens per case using a flattened ID `<TestName>_<Type>_c##` (e.g., `Riemann_Hydro_c00`).
- Discovery: the runner reads `regression_test/tests/<TestName>/configs` and expands each defined `Type` into one or more `cases`.
- Execution: `regression_test.py` iterates over these per-case units and runs compile → execute → fetch references → compare for each case.

### Detailed info
- Makefile options, MPI settings, tolerance levels, reference sources (local/cloud/url). See `regression_test/README.md` for details.

## Comparator and references
- Compare flow is per case and consists of three steps: fetch references → build/ensure compare tool → run comparisons.
- Reference providers support local, cloud, and URL. Cloud storage may retain legacy grouped layouts; providers adapt and stage files flat under `reference/`.
- HDF5 comparisons use a cached compare tool built under `regression_test/run/tools/<signature>/`.
