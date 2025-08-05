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


def main(rtvars: RuntimeVariables, test_configs, ch, file_handler, **kwargs):
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
    tests = [gamer.gamer_test(test_name, test_config, rtvars.gamer_path, ch, file_handler,
                              kwargs["error_level"]) for test_name, test_config in test_configs.items()]
    for test in tests:
        test.logger.info('Test %s start.' % (test.name))

        test.gh_has_list = has_version_list
        test.yh_folder_dict = ythub_folder_dict

        if test.run_all_cases(**kwargs) != STATUS.SUCCESS:
            continue
        if test.get_reference_data(**kwargs) != STATUS.SUCCESS:
            continue
        if test.make_compare_tool(**kwargs) != STATUS.SUCCESS:
            continue
        if test.compare_data(**kwargs) != STATUS.SUCCESS:
            continue
        if test.execute_scripts('user_compare_script', **kwargs) != STATUS.SUCCESS:
            continue

        has_version_list = test.gh_has_list
        ythub_folder_dict = test.yh_folder_dict

        test.logger.info('Test %s done.' % (test.name))

    return {test.name: {"status": test.status, "reason": test.reason} for test in tests}


def write_args_to_log(logger, **kwargs):
    logger.info("Record all arguments have been set.")
    for arg in kwargs:
        if arg == 'name':
            # msg = " ".join([NAME_INDEX[i] for i in kwargs[arg]])
            # logger.info("%-20s : %s" % ("test name (name)", msg))
            pass
        elif arg == 'type':
            # msg = " ".join([TYPE_INDEX[i] for i in kwargs[arg]])
            # logger.info("%-20s : %s" % ("test type (type)", msg))
            pass
        elif arg == "force_args":
            msg = " ".join(kwargs[arg])
            logger.info("%-20s : %s" % (arg, msg))
        elif type(kwargs[arg]) == str:   # string
            logger.info("%-20s : %s" % (arg, kwargs[arg]))
        elif type(kwargs[arg]) == int:   # integer
            logger.info("%-20s : %d" % (arg, kwargs[arg]))
        elif type(kwargs[arg]) == float:  # float
            logger.info("%-20s : %f" % (arg, kwargs[arg]))
        elif type(kwargs[arg]) == bool:  # boolean
            logger.info("%-20s : %r" % (arg, kwargs[arg]))
        else:
            logger.info("Unknown type: %s" % (arg))
    return


def output_summary(result):
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
    print("Please check <%s> for the detailed message." % args["output"])

    return fail_tests


def upload_process(test_configs, **kwargs):
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
    #     upload_process(test_configs, logger=kwargs['logger'])
    #     return

    # for test in tests_upload:
    #     print("Uploading test %s" % test)
    #     test_folder = GAMER_ABS_PATH + '/regression_test/tests/' + test
    #     gi.upload_data(test, GAMER_ABS_PATH, test_folder, logger=kwargs['logger'])

    return


####################################################################################################
# Main execution
####################################################################################################
if __name__ == '__main__':
    rtvars = RuntimeVariables(
        num_threads=os.cpu_count(),
        gamer_path=os.path.dirname(os.path.dirname(__file__)),
    )

    args, unknown_args = argument_handler()
    args = vars(args)

    test_explorer = TestExplorer(rtvars, args)

    GAMER_EXPECT_COMMIT = "13409ab33b12d84780076b6a9beb07317ca145f1"
    GAMER_CURRENT_COMMIT = get_git_info()

    # Initialize regression test
    test_configs, args = test_explorer.test_configs, test_explorer.input_args

    # Initialize logger
    ch, file_handler = log_init(args["output"])

    test_logger = set_up_logger('regression_test', ch, file_handler)

    test_logger.info('Recording the commit version.')
    test_logger.info('GAMER      version   : %-s' % (GAMER_CURRENT_COMMIT))

    if GAMER_CURRENT_COMMIT != GAMER_EXPECT_COMMIT:
        test_logger.warning('Regression test may not fully support this GAMER version!')

    write_args_to_log(test_logger, force_args=unknown_args, py_exe=sys.executable, **args)

    test_logger.info('Test to be run       : %-s' % (" ".join([name for name in test_configs])))

    # Regression test
    try:
        test_logger.info('Regression test start.')
        result = main(rtvars, test_configs, ch, file_handler, force_args=unknown_args, py_exe=sys.executable, **args)
        test_logger.info('Regression test done.')
    except Exception:
        test_logger.critical('', exc_info=True)
        raise

    # Print out short summary
    fail_tests = output_summary(result)

    # Further process for fail tests
    # TODO: add further process such as do nothing or accept new result and upload to hub.yt
    if fail_tests == {}:
        exit(0)
    if args['no-upload']:
        exit(1)

    print("========================================")
    upload_or_not = input("Would you like to update new result for fail test? (Y/n)")
    if upload_or_not in ['Y', 'y', 'yes']:
        upload_logger = set_up_logger('upload', ch, file_handler)
        upload_process(test_configs, logger=upload_logger)
    elif upload_or_not in ['N', 'n', 'no']:
        exit(1)
    else:
        raise ValueError("Invalid input: %s" % (upload_or_not))
