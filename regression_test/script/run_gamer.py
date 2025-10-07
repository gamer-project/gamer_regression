import logging
import os
import re
import subprocess
from os.path import isfile
from typing import Dict
from .models import TestCase
from .runtime_vars import RuntimeVariables
from .utilities import STATUS
from .process_runner import run_process


####################################################################################################
# Classes
####################################################################################################
class TestRunner:
    """Run a single TestCase (compile, copy, set inputs, pre/post, run GAMER)."""

    def __init__(self, rtvars: RuntimeVariables, case: TestCase, gamer_abs_path: str):
        self.case = case
        self.gamer_abs_path = gamer_abs_path
        self.src_path = os.path.join(gamer_abs_path, 'src')
        self.case_dir = case.run_dir(rtvars)
        self.ref_path = os.path.join(gamer_abs_path, 'example', 'test_problem', case.source)
        self.tool_path = os.path.join(gamer_abs_path, 'tool', 'analysis', 'gamer_compare_data')
        self.status = STATUS.SUCCESS
        self.reason = ""
        self.logger = logging.getLogger('runner')
        self.rtvar = rtvars
        self.timing = {}  # Store timing for each step
        return

    def compile_gamer(self):
        self.logger.info('Start compiling GAMER')

        # 1. Back up the original Makefile
        keep_makefile = isfile('Makefile')
        if keep_makefile:
            subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

        # 2. Get commands to modify Makefile.
        cmd = generate_modify_command(self.case.makefile_cfg, self.rtvar)

        try:
            self.logger.debug("Generating Makefile using: %s" % (" ".join(cmd)))
            run_process(cmd)
        except subprocess.CalledProcessError:
            self.set_fail_test("Error while editing Makefile.", STATUS.EDITING_FAIL)
            if keep_makefile:
                subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
                subprocess.check_call(['rm', 'Makefile.origin'])
            return self.status

        # 3. Compile GAMER
        try:
            run_process(['make', 'clean'])
            run_process('make -j', shell=True, tee_stdout='make.log', merge_streams=True)
            subprocess.check_call(['rm', 'make.log'])
        except subprocess.CalledProcessError:
            self.set_fail_test("Compiling error.", STATUS.COMPILE_ERR)
            return self.status

        finally:
            # Repair Makefile
            if keep_makefile:
                subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
                subprocess.check_call(['rm', 'Makefile.origin'])
            else:
                subprocess.check_call(['rm', 'Makefile'])

        # 4. Check if gamer exist
        if self.file_not_exist('./gamer'):
            return self.status

        self.logger.info('Compiling GAMER done.')

        return self.status

    def copy_case(self):
        """
        Copy input files and GAMER to work directory.
        """
        # TODO: Copy only necessary files (e.g., input files)
        case_dir = self.case_dir
        origin_dir = self.ref_path

        self.logger.info('Copying the test folder: %s ---> %s' % (origin_dir, case_dir))
        try:
            subprocess.check_call(['cp', '-r', origin_dir, case_dir])
            subprocess.check_call(['cp', os.path.join(self.src_path, 'gamer'), case_dir])
            subprocess.check_call(['cp', os.path.join(self.src_path, 'Makefile.log'), case_dir])
        except Exception:
            self.set_fail_test('Error when copying to %s.' % case_dir, STATUS.COPY_FILES)
        self.logger.info('Copy completed.')

        return self.status

    def set_input(self):
        # Merge only non-Makefile settings from the case model
        per_file_settings = {
            'Input__Parameter': self.case.input_parameter,
            'Input__TestProb': self.case.input_testprob,
        }
        for input_file, settings in per_file_settings.items():
            if not settings:
                continue
            self.logger.info('Editing %s.' % input_file)
            self._edit_input_file(input_file, settings)
            self.logger.info('Editing completed.')
        return self.status

    def execute_scripts(self, mode):
        self.logger.info('Start execute scripts. Mode: %s' % mode)
        if mode not in ['pre_script', 'post_script', 'user_compare_script']:
            self.set_fail_test("Wrong mode of executing scripts.", STATUS.FAIL)
            return self.status
        scripts = {
            'pre_script': self.case.pre_scripts,
            'post_script': self.case.post_scripts,
            'user_compare_script': self.case.user_compare_scripts,  # TODO: TestComparator need it.
        }[mode]
        for script in scripts:
            if self.file_not_exist(script):
                break
            try:
                self.logger.info('Executing: %s' % script)
                run_process(['sh', script, self.case_dir])
            except Exception:
                self.set_fail_test("Error while executing %s." % script, STATUS.EXTERNAL)
                break
        self.logger.info('Done execute scripts.')
        return self.status

    def run_gamer(self):
        run_mpi = False
        if "mpi" in self.case.makefile_cfg:
            run_mpi = self.case.makefile_cfg["mpi"]

        run_cmd = "mpirun -map-by ppr:%d:socket:pe=%d --report-bindings " % (
            self.rtvar.mpi_rank, self.rtvar.mpi_core_per_rank) if run_mpi else ""
        run_cmd += "./gamer"

        self.logger.info('Running GAMER.')
        try:
            # Stream into logging and tee to file 'log' for artifact
            run_process(run_cmd, shell=True, merge_streams=True, tee_stdout='log')
            if not isfile('./Record__Note'):
                self.set_fail_test('No Record__Note in %s.' % self.case.test_id, STATUS.FAIL)
        except subprocess.CalledProcessError:
            self.set_fail_test('GAMER error', STATUS.EXTERNAL)
        self.logger.info('GAMER done.')

        return self.status

    def set_fail_test(self, reason, status_type):
        self.status = status_type
        self.reason = reason
        self.logger.error(reason)
        return

    def file_not_exist(self, filename):
        if isfile(filename):
            return False
        reason = "%s does not exist." % filename
        self.set_fail_test(reason, STATUS.MISSING_FILE)
        return True

    def _edit_input_file(self, file_path, settings: Dict):
        """Strict in-place input file editor.
        Rules:
          * Ignore any line whose first non-space char is '#'. (commented-out keys are invisible)
          * For each key, modify only the existing line.
          * If any key is not found, fail the test.
          * Preserve original spacing and comment alignment:
              - Replace only the value token.
              - If a trailing comment exists, attempt to keep its column by shrinking/expanding
                the gap between value and '#'.
        """
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            self.set_fail_test(f'Missing input file {file_path}.', STATUS.MISSING_FILE)
            return

        missing_key = []
        for key, new_val in settings.items():
            matched = False
            key_regex = re.compile(r'^(\s*)' + re.escape(key) + r'(\s+)(\S+)(.*)$')
            for idx, line in enumerate(lines):
                stripped = line.lstrip()
                if not stripped or stripped.startswith('#'):
                    continue  # ignore commented / blank lines
                if not stripped.startswith(key):
                    continue  # line with different key
                m = key_regex.match(line.rstrip('\n'))  # strip only for regex
                if not m:
                    continue
                pre_spaces, space_after_key, old_val, rest = m.groups()
                # rest holds any spaces + comment (no newline)
                if '#' in rest:
                    before_comment, after_comment = rest.split('#', 1)
                    diff = len(str(new_val)) - len(old_val)  # difference in value length
                    if diff > 0:
                        before_comment = before_comment[diff:] if len(before_comment) > diff else ' '
                    elif diff < 0:
                        before_comment = before_comment + (' ' * (-diff))
                    rest_new = before_comment + '#' + after_comment
                else:
                    rest_new = rest
                lines[idx] = f"{pre_spaces}{key}{space_after_key}{new_val}{rest_new}\n"
                matched = True
                break
            if not matched:
                missing_key.append(key)
        if missing_key:
            self.set_fail_test(f"Keys not found in {file_path}: {', '.join(missing_key)}", STATUS.EDIT_FILE)
            return
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines)
        except Exception:
            self.set_fail_test(f"Error on editing {file_path}.", STATUS.EDIT_FILE)


####################################################################################################
# Functions
####################################################################################################
def generate_modify_command(config, rtvars: RuntimeVariables):
    """
    Edit gamer configuration settings.

    Parameters
    ----------

    config :
        config of the options to be modified.

    Returns
    -------

    cmd    :
        command
    """
    cmd = [rtvars.py_exe, "configure.py"]
    # 0. machine configuration
    cmd.append("--machine="+rtvars.machine)

    # 1. simulation and miscellaneous options
    for key, val in config.items():
        cmd.append("--%s=%s" % (key, val))

    # 2. user force enable options
    # cmd.append("--hdf5=True")  # Enable HDF5 in all test
    # for arg in kwargs["force_args"]:
    #    cmd.append(arg)

    return cmd
