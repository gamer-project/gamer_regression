# Copilot Instructions for gamer_regression

## Project Overview
- **GAMER**: GPU-accelerated Adaptive Mesh Refinement code for astrophysical simulations.
- There are two part of code in the workspace: the main code in `src/` and the regression test code in `regression_test/` (Main development focus).

## Regression Testing
For VSCode Copilot:
   - Run `conda activate regression` to activate the environment.
   - `--machine=perlmutter`
For GitHub Coding Agent:
   - `--machine=github_action`

- For smoke test, run `python regression_test/regression_test.py --machine=<SEEABOVE> -u --tags CYC AcousticWave -o quick_test`
- For full test, run `python regression_test/regression_test.py --machine=<SEEABOVE> --tags CYC` to start the regression tests (~30 mins).
- Note: Since the tests are still in development, it is normal that all the tests failed.

## Best practices
- Run the smoke test to check if your modifications works.

## Regression Test Structure

### Files
1. **`regression_test.py`**
   - Entry point for running regression tests.

### Folders
1. **`run/`** Directory for running regression tests
   - The structure under it is `path/name` set by the config yaml files.

2. **`script/`** The source code of the regression test.

3. **`tests/`** Test problem definitions and configs.
- Test cases are defined in `regression_test/tests/*.yaml` files.
- A tree of nodes are defined in each YAML file, each leave node is a `TestCase`.

4. **`references/`** Reference data for comparison.
- Subfolders `local/` and `cloud/` store and cache reference data, respectively.
- Path under `local/` and `cloud/` are identical to the path under `run/`.

## Quick mental model for tests
- Execution: `regression_test.py` iterates over these per-case units and runs compile → execute → fetch references → compare for each case.
- HDF5 comparisons use a cached compare tool built under `regression_test/run/tools/<signature>/`.
