from __future__ import print_function
from script.utilities import STATUS, read_test_config, set_up_logger
import script.run_gamer as gamer
import script.girder_inscript as gi
import argparse
import os
import sys
import logging
import subprocess
from os import listdir
from os.path import isfile

from script.argparse import argument_handler
from script.test_explorer import TestExplorer
from script.models import TestCase
from typing import List
from script.runtime_vars import RuntimeVariables


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
# Global variables
####################################################################################################
# 3. Logging variable
STD_FORMATTER = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-20s : %(message)s')
SAVE_FORMATTER = logging.Formatter('%(levelname)-8s %(name)-20s %(message)s')


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


def log_init(log_file_name):
    """
    Initialize the logger.

    Returns
    -------

    ch           : class logging.StreamHandler
       Saving the screen output format to the logger.
    file_handler : class logging.FileHandler
       Saving the file output format to the logger.
    """
    # 1. Set up log config
    logging.basicConfig(level=0)

    ch = logging.StreamHandler()
    file_handler = logging.FileHandler(log_file_name)

    # 2. Add log config into std output
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(STD_FORMATTER)

    # 3. Add log config into file
    file_handler.setLevel(0)
    file_handler.setFormatter(SAVE_FORMATTER)

    return ch, file_handler


def main(rtvars: RuntimeVariables, test_cases: List[TestCase], ch, file_handler):
    """
    Main regression test.

    Parameters
    ----------

    tests        : dict
       A dictionary of a sequence of the test paths with a key access of the test names.
    ch           : class logging.StreamHandler
       Saving the screen output format to the logger.
    file_handler : class logging.FileHandler
       Saving the file output format to the logger.
    """

    has_version_list = False
    ythub_folder_dict = {}
    # Group by <TestName>_<Type> and run per-case via TestRunner
    grouped_cfg = {}
    grouped_cases: dict[str, list[TestCase]] = {}
    for tc in test_cases:
        key = tc.test_key
        if key not in grouped_cfg:
            grouped_cfg[key] = {
                "name": tc.problem_name,
                "pre_script": tc.pre_scripts,
                "post_script": tc.post_scripts,
                "user_compare_script": tc.user_compare_scripts,
                "reference": [
                    {"name": r.name, "loc": r.loc, "file_type": r.file_type} for r in tc.references
                ],
                "levels": tc.levels,
                "cases": [],  # still needed by gamer_test.make_compare_tool
            }
            grouped_cases[key] = []
        grouped_cfg[key]["cases"].append({
            "Makefile": tc.makefile_cfg,
            "Input__Parameter": tc.input_parameter,
            "Input__TestProb": tc.input_testprob,
        })
        grouped_cases[key].append(tc)

    results = {}
    for name, cfg in grouped_cfg.items():
        # Prepare run group dir and assign to cases
        run_group_dir = os.path.join(rtvars.gamer_path, 'regression_test', 'run', name)
        if os.path.isdir(run_group_dir):
            subprocess.check_call(['rm', '-rf', run_group_dir])
        os.makedirs(run_group_dir)

        # Run each case directly with TestRunner
        for tc in grouped_cases[name]:
            tc.run_group_dir = run_group_dir
            runner = gamer.TestRunner(rtvars, tc, rtvars.gamer_path, ch, file_handler)
            test_logger = set_up_logger(name, ch, file_handler)
            test_logger.info('Start running case: %s' % tc.case_name)
            os.chdir(os.path.join(rtvars.gamer_path, 'src'))
            if runner.compile_gamer() != STATUS.SUCCESS:
                results[name] = {"status": runner.status, "reason": runner.reason}
                break
            if runner.copy_case() != STATUS.SUCCESS:
                results[name] = {"status": runner.status, "reason": runner.reason}
                break
            os.chdir(runner.case_dir)
            if runner.set_input() != STATUS.SUCCESS:
                results[name] = {"status": runner.status, "reason": runner.reason}
                break
            if runner.execute_scripts('pre_script') != STATUS.SUCCESS:
                results[name] = {"status": runner.status, "reason": runner.reason}
                break
            if runner.run_gamer() != STATUS.SUCCESS:
                results[name] = {"status": runner.status, "reason": runner.reason}
                break
            if runner.execute_scripts('post_script') != STATUS.SUCCESS:
                results[name] = {"status": runner.status, "reason": runner.reason}
                break

        # Group-level operations with legacy gamer_test
        test = gamer.gamer_test(rtvars, name, cfg, rtvars.gamer_path, ch, file_handler)
        test.logger.info('Test %s start.' % (test.name))

        test.gh_has_list = has_version_list
        test.yh_folder_dict = ythub_folder_dict

        if test.get_reference_data() == STATUS.SUCCESS and \
           test.make_compare_tool() == STATUS.SUCCESS and \
           test.compare_data() == STATUS.SUCCESS and \
           test.execute_scripts('user_compare_script') == STATUS.SUCCESS:
            results[name] = {"status": test.status, "reason": test.reason}
        else:
            results[name] = {"status": test.status, "reason": test.reason}

        has_version_list = test.gh_has_list
        ythub_folder_dict = test.yh_folder_dict

        test.logger.info('Test %s done.' % (test.name))

    return results


def write_args_to_log(logger, rtvars: RuntimeVariables, force_args=None):
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


def upload_process(test_configs, logger):
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
        gamer_path=os.path.dirname(os.path.dirname(__file__)),
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

    if isfile(rtvars.output):
        print('WARNING!!! %s is already exist. The original log file will be removed.' % (rtvars.output))
        os.remove(rtvars.output)

    test_explorer = TestExplorer(rtvars)

    GAMER_EXPECT_COMMIT = "13409ab33b12d84780076b6a9beb07317ca145f1"
    GAMER_CURRENT_COMMIT = get_git_info()

    # Initialize regression test
    # Use new flat list of cases produced by TestExplorer
    test_cases = test_explorer.get_test_cases()

    # Initialize logger
    ch, file_handler = log_init(rtvars.output)

    test_logger = set_up_logger('regression_test', ch, file_handler)

    test_logger.info('Recording the commit version.')
    test_logger.info('GAMER      version   : %-s' % (GAMER_CURRENT_COMMIT))

    if GAMER_CURRENT_COMMIT != GAMER_EXPECT_COMMIT:
        test_logger.warning('Regression test may not fully support this GAMER version!')

    write_args_to_log(test_logger, rtvars, force_args=unknown_args)

    keys = sorted(set(tc.test_key for tc in test_cases))
    test_logger.info('Test to be run       : %-s' % (" ".join(keys)))

    # Regression test
    try:
        test_logger.info('Regression test start.')
        result = main(rtvars, test_cases, ch, file_handler)
        test_logger.info('Regression test done.')
    except Exception:
        test_logger.critical('', exc_info=True)
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
        upload_logger = set_up_logger('upload', ch, file_handler)
        upload_process({}, upload_logger)
    elif upload_or_not in ['N', 'n', 'no']:
        exit(1)
    else:
        raise ValueError("Invalid input: %s" % (upload_or_not))
