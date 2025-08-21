import logging
import os
import subprocess
from os.path import isfile
from .log_pipe import LogPipe
from .models import TestCase
from .runtime_vars import RuntimeVariables
from .utilities import STATUS, set_up_logger


####################################################################################################
# Classes
####################################################################################################
class TestRunner:
    """Run a single TestCase (compile, copy, set inputs, pre/post, run GAMER)."""

    def __init__(self, rtvars: RuntimeVariables, case: TestCase, gamer_abs_path: str, ch, file_handler):
        self.case = case
        self.err_level = rtvars.error_level
        self.gamer_abs_path = gamer_abs_path
        self.src_path = os.path.join(gamer_abs_path, 'src')
        # per-case run dir provided by orchestrator
        self.group_dir = None
        self.case_dir = case.run_dir
        self.ref_path = os.path.join(gamer_abs_path, 'regression_test', 'tests', case.problem_name)
        self.tool_path = os.path.join(gamer_abs_path, 'tool', 'analysis', 'gamer_compare_data')
        self.status = STATUS.SUCCESS
        self.reason = ""
        self.logger = set_up_logger(f"{case.test_id}", ch, file_handler)
        self.rtvar = rtvars
        return

    def compile_gamer(self):
        self.logger.info('Start compiling GAMER')
        out_log = LogPipe(self.logger, logging.DEBUG)

        # 1. Back up the original Makefile
        keep_makefile = isfile('Makefile')
        if keep_makefile:
            subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

        # 2. Get commands to modify Makefile.
        cmd = generate_modify_command(self.case.makefile_cfg, self.rtvar)

        try:
            self.logger.debug("Generating Makefile using: %s" % (" ".join(cmd)))
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError:
            self.set_fail_test("Error while editing Makefile.", STATUS.EDITING_FAIL)
            if keep_makefile:
                subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
                subprocess.check_call(['rm', 'Makefile.origin'])
            out_log.close()
            return self.status

        # 3. Compile GAMER
        try:
            subprocess.check_call(['make', 'clean'], stderr=out_log)
            subprocess.check_call(['make -j > make.log'], stderr=out_log, shell=True)
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

            out_log.close()

        # 4. Check if gamer exist
        if self.file_not_exist('./gamer'):
            return self.status

        self.logger.info('Compiling GAMER done.')

        return self.status

    def copy_case(self):
        """
        Copy input files and GAMER to work directory.
        """
        case_dir = self.case_dir
        origin_dir = os.path.join(self.ref_path, 'Inputs')

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
            cmds = []

            for key, val in settings.items():
                cmds.append(['sed', '-i', 's/%-29s/%-29s%-4s #/g' % (key, key, val), input_file])

            self.logger.info('Editing %s.' % input_file)
            try:
                for cmd in cmds:
                    subprocess.check_call(cmd)
            except:
                self.set_fail_test('Error on editing %s.' % input_file, STATUS.EDIT_FILE)
            self.logger.info('Editing completed.')

        return self.status

    def execute_scripts(self, mode):
        self.logger.info('Start execute scripts. Mode: %s' % mode)
        if mode not in ['pre_script', 'post_script', 'user_compare_script']:
            self.set_fail_test("Wrong mode of executing scripts.", STATUS.FAIL)
            return self.status

        out_log = LogPipe(self.logger, logging.DEBUG)
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
                subprocess.check_call(['sh', script, self.case_dir], stderr=out_log)
            except:
                self.set_fail_test("Error while executing %s." % script, STATUS.EXTERNAL)
                break
        out_log.close()
        self.logger.info('Done execute scripts.')
        return self.status

    def run_gamer(self):
        out_log = LogPipe(self.logger, logging.DEBUG)
        run_mpi = False
        if "mpi" in self.case.makefile_cfg:
            run_mpi = self.case.makefile_cfg["mpi"]

        run_cmd = "mpirun -map-by ppr:%d:socket:pe=%d --report-bindings " % (
            self.rtvar.mpi_rank, self.rtvar.mpi_core_per_rank) if run_mpi else ""
        run_cmd += "./gamer 1>>log 2>&1"

        self.logger.info('Running GAMER.')
        try:
            subprocess.check_call([run_cmd], stderr=out_log, shell=True)
            if not isfile('./Record__Note'):
                self.set_fail_test('No Record__Note in %s.' % self.case.test_id, STATUS.FAIL)
        except subprocess.CalledProcessError as err:
            self.set_fail_test('GAMER error', STATUS.EXTERNAL)
        finally:
            out_log.close()
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
