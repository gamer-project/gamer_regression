## Deep dive: regression_test/tests anatomy

### Test directory layout (per test)
Each test lives under `regression_test/tests/<TestName>/` and generally contains:
- `Inputs/`
  - Baseline input files copied into each run case directory:
    - `Input__Parameter`
    - `Input__TestProb`
    - Optional flags: `Input__Flag_Lohner`, `Input__Flag_User`, `Input__Flag_Rho`, `Input__Flag_NParPatch`, etc.
    - Helper scripts like `clean.sh`, `user_analyze.sh`, and sometimes `inline_script.py` used by pre/post steps.
- `configs`
  - YAML file defining test types, cases, error levels, pre/post scripts, and reference data.

Notes
- Case run folders are created under `regression_test/run/<TestName>/{case_00,case_01,...}`.
- For reference data pulled from cloud, a local mirror is built under `<run>/<TestName>/reference/`.

### Config YAML schema (authoring guide)
Top-level: one or more test types per test (keys like `Hydro`, `MHD`, `SRHD`, `Gravity`, `Particle`, `L1Error`).
- `priority`: one of `high|medium|low`. Only types with priority >= selected runtime priority are included.
- `levels`: numeric tolerances keyed by `level0..level3`. Used by comparisons.
- `cases`: list of case objects executed in order as `case_00`, `case_01`, ...
  - `Makefile`: dict of build-time options mapped 1:1 to `configure.py` flags, e.g.:
    - Common: `model: HYDRO|ELBDM`, `double: true`, `debug: true`, `hdf5: true`, `gpu: true`, `mpi: true`, `bitwise_reproducibility: true`, `timing: true`
    - Physics: `mhd: true`, `gravity: true`, `particle: true`, `fftw: FFTW3`, `srhd: true`
    - Schemes (Riemann/SRHD): `flu_scheme: MHM`, `slope: PLM`, `flux: HLLC`
  - `Input__Parameter`: dict of parameter overrides applied in-place to the copied file via `sed -i` pattern.
  - `Input__TestProb`: dict of problem-specific overrides applied similarly.
- `pre_script`: list of shell scripts to run before GAMER. They receive the case run dir as the first arg.
- `post_script`: list of shell scripts to run after GAMER.
- `reference`: list of files to compare. Each item:
  - `name`: path relative to the case run dir (e.g., `case_00/Data_000010`, `case_00/Record__Note`).
  - `loc`: `local:<path>` to symlink a local file, or `cloud:<relative>` to fetch from hub.yt. `url:` is parsed but not supported.
  - `file_type`: `HDF5|TEXT|NOTE` selects the comparator.
- `user_compare_script`: optional extra comparison scripts run after built-in comparisons.

Schema examples in repo
- `AcousticWave/configs`: types `Hydro`, `L1Error` (TEXT + NOTE comparisons, MPI in L1Error).
- `BlastWave/configs`: types `Hydro`, `MHD` (HDF5, TEXT, NOTE).
- `MHD_ABC/configs`: type `MHD` (GPU+MPI+HDF5).
- `Plummer/configs`: types `Gravity`, `Particle` (HDF5, TEXT, NOTE with FFTW, particle on).
- `Riemann/configs`: types `Hydro`, `MHD`, `SRHD` (TEXT Xline outputs + NOTE; multiple cases via YAML anchors).
- `Template/configs`: minimal template with placeholders and comments.

### Case lifecycle (what the runner does)
For each selected `<TestName>_<Type>`:
1) Compile
- Generate `src/Makefile` via `python configure.py` using `cases[N].Makefile` and runtime overrides.
- `make clean && make -j` in `src/`; build logs streamed into the per-test logger.
- Restore original `Makefile` afterwards.

2) Stage case dir
- Create `regression_test/run/<TestName>/case_##/`.
- Copy `tests/<TestName>/Inputs` directory into the case folder and also copy `src/gamer` and `src/Makefile.log`.

3) Patch inputs
- For each key in `Input__Parameter` and `Input__TestProb`, run `sed -i` replacements. Keys must match the left-hand names exactly as in files (fixed-width formatting expected by the pattern).

4) Pre scripts
- Run each script in `pre_script` as `sh <script> <run_case_dir>`. Paths are resolved relative to the case dir.

5) Execute GAMER
- If `Makefile.mpi` is true: run with `mpirun -map-by ppr:<mpi_rank>:socket:pe=<mpi_core_per_rank>` then `./gamer >> log`.
- Otherwise run `./gamer >> log`.
- Require `Record__Note` to exist after run.

6) Post scripts
- Run each script in `post_script` on the case dir.

7) Reference fetch
- For each `reference` entry:
  - `local:` create symlink into `<run>/<TestName>/reference/` (preserving per-case subdirs if present in `name`).
  - `cloud:` resolve latest version via hub.yt compare list and download into the same mirror location.

8) Compare
- `TEXT`: load with numpy and compare max abs diff to `levels[error_level]`.
- `HDF5`: compile `tool/analysis/gamer_compare_data` Makefile on the fly using `configs/<machine>.config` paths, then run `GAMER_CompareData -i <result> -j <expect> -o compare_result -e <tol> -c -m` and check `compare_result`.
- `NOTE`: parse both `Record__Note` files into section/parameter maps and diff key/value pairs; currently non-fatal.
- Run any `user_compare_script` items.

### Pathing and scripting conventions (important)
- Script resolution for `pre_script/post_script/user_compare_script` is relative to the case dir. In practice many tests place `clean.sh` inside `Inputs/`; in that case, set the script path as `Inputs/clean.sh` in the YAML.
- The runner passes the absolute case path as `$1` to scripts; write scripts to treat `$1` as the workspace root for that case.
- Input patching assumes each key appears exactly once and follows the GAMER input line formatting (name field padded to width ~29). Mismatched keys won’t be updated.

### Reference data locations
- `local:` accepts absolute or relative paths; relative is resolved from the current working dir during fetch. Prefer absolute paths for stability in CI.
- `cloud:` uses Girder (hub.yt). The latest version for a given `<TestName>` is chosen from `regression_test/compare_version_list/compare_list` and then the specific file is pulled by walking the stored folder tree.

### Existing tests and their types in this repo
- `AcousticWave`: `Hydro`, `L1Error`
- `BlastWave`: `Hydro`, `MHD`
- `MHD_ABC`: `MHD`
- `Plummer`: `Gravity`, `Particle`
- `Riemann`: `Hydro`, `MHD`, `SRHD`
- `Template`: example schema only (excluded by the runner)

### Common pitfalls and tips
- Put scripts where the runner can find them. Either place them at the case root (copied separately) or reference them with their `Inputs/` path (recommended: keep scripts in `Inputs/`).
- When enabling `HDF5` comparisons, ensure the case Makefile sets `hdf5: true`; the compare tool build also toggles `-DSUPPORT_HDF5` accordingly.
- For MPI runs, adjust CLI flags `--mpi_rank` and `--mpi_core_per_rank` to match node topology; otherwise mpirun binding may fail.
- Keep YAML anchors/aliases for repeated case blocks (see `Riemann/configs`), but ensure each case still defines any differing `Input__*` overrides.
- `url:` references are parsed but not supported; use `cloud:` or `local:`.
- The NOTE comparison is informational; it won’t currently fail the test even when differences exist.
