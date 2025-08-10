
# Copilot Instructions for gamer_regression

## Project Overview
- **GAMER**: GPU-accelerated Adaptive Mesh Refinement code for astrophysical simulations. The main code is in `src/`.
- There are two part in the workspace: the main code and the regression test code.
- Main development focus: `regression_test/` (active development, main area for contributions).

## VS Code Environment
- Dependency setup is already complete; do not modify or re-run environment setup scripts.

## Regression Testing
- Main entry: `regression_test/regression_test.py`.
- Use `conda activate regression` to activate the conda environment for regression testing when you open a new terminal.
- Test logic is (partially) modular; see `regression_test/script/` submodules.

## Examples
- Run regression tests: run `python regression_test/regression_test.py --machine=perlmutter`. Since the tests structure are still in development, it is normal that all the tests failed.

## Best practices
- Run the regression test to check if your modifications works.
