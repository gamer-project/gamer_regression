import logging
import os
import sys
import subprocess
from typing import List
from script.argparse import argument_handler
from script.comparator import TestComparator, CompareToolBuilder
from script.logging_center import log_init, set_log_context, clear_log_context
from script.models import TestCase
from script.run_gamer import TestRunner
from script.runtime_vars import RuntimeVariables
from script.test_explorer import TestExplorer
from script.utilities import STATUS


"""
TODO:
1. rename variables
2. remove the unused variables
3. clean every thing about the path

Documents:
1. the file structure is assumed
2. how to add a test
3. how to modify
4. the logic of regression test
"""


####################################################################################################
# Functions
####################################################################################################
def get_git_info():
    """
    Get the current gamer hash.

    Returns
    -------

    gamer_commit      : str
       gamer commit hash
    """
    try:
        gamer_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except:
        gamer_commit = "UNKNOWN"

    return gamer_commit


def main(rtvars: RuntimeVariables, test_cases: List[TestCase]):
    """
    Main regression test.

    Parameters
    ----------

    tests        : dict
       A dictionary of a sequence of the test paths with a key access of the test names.
    """

    results: dict[str, dict] = {}
    tool_builder = CompareToolBuilder(rtvars)
    comparator = TestComparator(rtvars, tool_builder)

    for tc in test_cases:
        # Prepare per-case run dir
        logger = logging.getLogger('runner')
        run_dir = tc.run_dir(rtvars)
        if os.path.isdir(run_dir):
            subprocess.check_call(['rm', '-rf', run_dir])
            logger.warning(f"Run directory {run_dir} exists. Removed.")
        os.makedirs(os.path.dirname(run_dir), exist_ok=True)

        # Run case
        runner = TestRunner(rtvars, tc, rtvars.gamer_path)
        try:
            set_log_context(test_id=tc.test_id, phase='start')
            logger.info('Start running case')

            set_log_context(phase='compile')
            os.chdir(os.path.join(rtvars.gamer_path, 'src'))
            if runner.compile_gamer() != STATUS.SUCCESS:
                results[tc.test_id] = {"status": runner.status, "reason": runner.reason}
                continue

            set_log_context(phase='prepare')
            if runner.copy_case() != STATUS.SUCCESS:
                results[tc.test_id] = {"status": runner.status, "reason": runner.reason}
                continue

            set_log_context(phase='set_input')
            os.chdir(runner.case_dir)
            if runner.set_input() != STATUS.SUCCESS:
                results[tc.test_id] = {"status": runner.status, "reason": runner.reason}
                continue

            set_log_context(phase='pre_script')
            if runner.execute_scripts('pre_script') != STATUS.SUCCESS:
                results[tc.test_id] = {"status": runner.status, "reason": runner.reason}
                continue

            set_log_context(phase='run')
            if runner.run_gamer() != STATUS.SUCCESS:
                results[tc.test_id] = {"status": runner.status, "reason": runner.reason}
                continue

            set_log_context(phase='post_script')
            if runner.execute_scripts('post_script') != STATUS.SUCCESS:
                results[tc.test_id] = {"status": runner.status, "reason": runner.reason}
                continue

            # Compare
            set_log_context(phase='compare')
            status, reason = comparator.compare(tc, rtvars.error_level)
            results[tc.test_id] = {"status": status, "reason": reason}
            logger.info('Case done')
        finally:
            clear_log_context()

    return results


def write_args_to_log(rtvars: RuntimeVariables, force_args=None):
    logger = logging.getLogger('main')
    logger.info("Record all arguments have been set.")
    # force/unknown args first if provided
    if force_args:
        logger.info("%-20s : %s" % ("force_args", " ".join(force_args)))

    # Log fields from rtvars dataclass
    for field, value in vars(rtvars).items():
        if isinstance(value, str):
            logger.info("%-20s : %s" % (field, value))
        elif isinstance(value, int):
            logger.info("%-20s : %d" % (field, value))
        elif isinstance(value, float):
            logger.info("%-20s : %f" % (field, value))
        elif isinstance(value, bool):
            logger.info("%-20s : %r" % (field, value))
        else:
            logger.info("%-20s : %s" % (field, value))
    return


def output_summary(result, log_file):
    TEXT_RED = "\033[91m"
    TEXT_GREEN = "\033[92m"
    TEXT_RESET = "\033[0m"
    SEP_LEN = 50
    OUT_FORMAT = "%-20s: %-15s %s"
    print("="*SEP_LEN)
    print("Short summary: (Fail will be colored as red, passed will be colored as green.)")
    print("="*SEP_LEN)
    print(OUT_FORMAT % ("Test name", "Error code", "Reason"))

    fail_tests = {}
    summary = ""
    for key, val in result.items():
        if val["status"] != STATUS.SUCCESS:
            fail_tests[key] = val["status"]
        summary += TEXT_GREEN if val["status"] == STATUS.SUCCESS else TEXT_RED
        summary += OUT_FORMAT % (key, STATUS.CODE_TABLE[val["status"]], val["reason"])
        summary += TEXT_RESET
        summary += "\n"

    print(summary, end="")
    print("="*SEP_LEN)
    print("Please check <%s> for the detailed message." % log_file)

    return fail_tests


def upload_process(test_configs):
    # logger = logging.getLogger('upload')
    # tests_to_upload = input("Enter tests you'd like to update result. ")
    # tests_upload = tests_to_upload.split()

    # reask = False
    # for test_upload in tests_upload:
    #     if test_upload not in ALL_TEST_CONFIGS:
    #         print("'%s' no such test.")
    #         reask = True
    #     elif test_upload not in test_configs:
    #         print("%s is not included in the tests you have ran.")
    #         reask = True
    # if reask:
    #     upload_process(test_configs, logger)
    #     return

    # for test in tests_upload:
    #     print("Uploading test %s" % test)
    #     test_folder = GAMER_ABS_PATH + '/regression_test/tests/' + test
    #     gi.upload_data(test, GAMER_ABS_PATH, test_folder, logger)

    return


####################################################################################################
# Main execution
####################################################################################################
if __name__ == '__main__':
    args, unknown_args = argument_handler()

    rtvars = RuntimeVariables(
        num_threads=os.cpu_count(),
        gamer_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        py_exe=sys.executable,
        error_level=args.error_level,
        priority=args.priority,
        name=args.name,
        type=args.type,
        output=args.output + ".log",
        no_upload=args.no_upload,
        machine=args.machine,
        mpi_rank=args.mpi_rank,
        mpi_core_per_rank=args.mpi_core_per_rank
    )

    test_explorer = TestExplorer(rtvars)

    GAMER_EXPECT_COMMIT = "13409ab33b12d84780076b6a9beb07317ca145f1"
    GAMER_CURRENT_COMMIT = get_git_info()

    # Initialize regression test
    # Use new flat list of cases produced by TestExplorer
    test_cases = test_explorer.get_test_cases()

    # Initialize logger
    log_init(rtvars.output)

    logger = logging.getLogger('main')

    logger.info('Recording the commit version.')
    logger.info('GAMER      version   : %-s' % (GAMER_CURRENT_COMMIT))

    if GAMER_CURRENT_COMMIT != GAMER_EXPECT_COMMIT:
        logger.warning('Regression test may not fully support this GAMER version!')

    write_args_to_log(rtvars, force_args=unknown_args)

    keys = sorted(tc.test_id for tc in test_cases)
    logger.info('Test to be run       : %-s' % (" ".join(keys)))

    # Regression test
    try:
        logger.info('Regression test start.')
        result = main(rtvars, test_cases)
        logger.info('Regression test done.')
    except Exception:
        logger.exception('Unexpected Error')
        raise

    # Print out short summary
    fail_tests = output_summary(result, rtvars.output)

    # Further process for fail tests
    # TODO: add further process such as do nothing or accept new result and upload to hub.yt
    if fail_tests == {}:
        exit(0)
    if rtvars.no_upload:
        exit(1)

    print("========================================")
    upload_or_not = input("Would you like to update new result for fail test? (Y/n)")
    if upload_or_not in ['Y', 'y', 'yes']:
        upload_process({})
    elif upload_or_not in ['N', 'n', 'no']:
        exit(1)
    else:
        raise ValueError("Invalid input: %s" % (upload_or_not))
