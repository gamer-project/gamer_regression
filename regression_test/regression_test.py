from __future__ import print_function
import argparse
import os
import sys
import logging
import logging.config
import subprocess
from os import listdir
from os.path import isfile, isdir, join

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

#import script.girder_handler as gh
import script.girder_inscript as gi
import script.run_gamer as gamer
from   script.utilities import *



####################################################################################################
# Global variables
####################################################################################################
# 1. Paths
CURRENT_ABS_PATH     = os.getcwd()
GAMER_ABS_PATH       = os.path.dirname( CURRENT_ABS_PATH )
gamer.gamer_abs_path = GAMER_ABS_PATH

# 2. Test problem
test_example_path = GAMER_ABS_PATH + '/regression_test/tests'
ALL_TESTS = { direc:test_example_path+'/'+direc+'/Inputs' for direc in listdir(test_example_path) }
ALL_TESTS.pop('Template')                 # Remove the Template folder from test
ALL_GROUPS = gamer.read_yaml( GAMER_ABS_PATH + "/regression_test/group", 'test_list' )

TEST_INDEX  = [ t for t in ALL_TESTS  ]   # Set up index of tests
GROUP_INDEX = [ g for g in ALL_GROUPS ]   # Set up index of groups

# 3. Logging variable
STD_FORMATTER  = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
SAVE_FORMATTER = logging.Formatter('%(levelname)-8s %(name)-15s %(message)s')

# 4. MPI variables
thread_nums     = os.cpu_count()
THREAD_PER_CORE = 2
CORE_PER_RANK   = 8
core_nums       = thread_nums // THREAD_PER_CORE
RANK_NUMS       = core_nums   // CORE_PER_RANK



####################################################################################################
# Functions
####################################################################################################
def argument_handler():
    """
    Get the input arguements.

    Returns
    -------

    args    : class argparse.Namespace
       Storing the input arguments.

    unknown : list of string
       Storing the unknown argument input.

    """

    test_msg = "Extra test index:\n"
    test_msg += "".join( ["  %2d : %-20s\n"%(i, t) for i, t in enumerate(TEST_INDEX)] )
    test_msg += "Group index:\n"
    for g in range(len(ALL_GROUPS)):
        key, val = list(ALL_GROUPS.items())[g]
        test_msg += "  %2d : %-20s => %s\n"%( g, key, ", ".join(["%s"%t for t in val["tests"]]) )

    parser = argparse.ArgumentParser( description = "Regression test of GAMER.",
                                      formatter_class = argparse.RawTextHelpFormatter,
                                      epilog = test_msg,
                                      allow_abbrev=False        # python version must be >= 3.5
                                      )

    parser.add_argument( "--error_level",
                         help="Error allowed in this test. \nDefault: %(default)s",
                         type=str, choices=["level0", "level1", "level2"],
                         default="level0"
                       )
    parser.add_argument( "-p", "--path",
                         help="Set the path of the GAMER path. \nDefault: %(default)s",
                         type=str,
                         default=GAMER_ABS_PATH
                       )
    parser.add_argument( "-g", "--group",
                         help="Specify test group to run. \nDefault: %(default)s",
                         nargs="+",
                         type=int,
                         default=[]
                       )
    parser.add_argument( "-t", "--test",
                         help="Specify tests to run. \nDefault: %(default)s",
                         nargs="+",
                         type=int,
                         default=[]
                       )
    parser.add_argument( "-o", "--output",
                         help="Set the file name of the test log. The output file will add a suffix '.log' automatically. \nDefault: %(default)s",
                         type=str,
                         default="test"
                       )

    parser.add_argument("--machine",
                        help="Select the machine configuration in ../configs. \nDefault: %(default)s",
                        default="eureka_intel")

    # MPI arguments
    parser.add_argument( "--mpi",
                         help="Force running run with open-mpi for all tests. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )
    parser.add_argument( "--mpi_rank", metavar="N_RANK",
                         help="Number of ranks of mpi. \nDefault: %(default)s",
                         type=int,
                         default=RANK_NUMS
                       )
    parser.add_argument( "--mpi_core_per_rank", metavar="N_CORE",
                         help="Core used per rank. \nDefault: %(default)s",
                         type=int,
                         default=CORE_PER_RANK
                       )

    # GPU arguments
    parser.add_argument( "--gpu",
                         help="Force running run with gpu for all tests. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )
    parser.add_argument( "--gpu_arch",
                         help="Specify the gpu architecture. \nDefault: %(default)s",
                         type=str,
                         default=get_gpu_arch()
                       )

    # Others
    parser.add_argument( "--hide_make",
                         help="Hide the make messages. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )

    args, unknown = parser.parse_known_args()

    # Print out the unknown arguments
    if unknown != []: print("Simulation forced or unknown arguments: ", unknown)

    return args, unknown


def get_git_info():
    """
    Get the current gamer and regression hash.

    Returns
    -------

    gamer_commit      : str
       gamer commit hash
    regression_commit : str
       regression commit hash
    """
    try:
        regression_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except:
        regression_commit = "UNKNOWN"
    os.chdir( GAMER_ABS_PATH )
    try:
        gamer_commit      = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except:
        gamer_commit      = "UNKNOWN"
    os.chdir( CURRENT_ABS_PATH )

    return gamer_commit, regression_commit


def reg_init( input_args ):
    """
    Initialize the regression test.

    Inputs
    ------

    input_args   : dict
       A dictionary contains the regression parameters.

    Returns
    -------

    testing_test : list
       A list contains strings of test name which to be tested.
    """
    global GAMER_ABS_PATH

    testing_groups, group_options = {}, {}

    # 0. Setting the default test group
    # if nothing input, run group 0 which include all tests
    if len(input_args["group"]) == 0 and len(input_args["test"]) == 0:
        input_args["group"] = [0]

    # 1. Check if the input arguments are valid.
    for idx_g in input_args["group"]:
        if idx_g < 0 or idx_g > len(ALL_GROUPS):
            print("Unrecognize index of the group: %d"%idx_g)
            continue

        group_tests = ALL_GROUPS[GROUP_INDEX[idx_g]]["tests"]
        group_options[GROUP_INDEX[idx_g]] = ALL_GROUPS[GROUP_INDEX[idx_g]]["options"]
        testing_tests  = {}
        for test in group_tests:
            testing_tests[test] = ALL_TESTS[test]

        testing_groups[GROUP_INDEX[idx_g]] = testing_tests

    testing_tests  = {}
    for idx in input_args["test"]:
        if idx >= len(TEST_INDEX) or idx < 0:
            print("Unrecognize index of the test: %d"%idx)
            continue
        testing_tests[TEST_INDEX[idx]] = ALL_TESTS[TEST_INDEX[idx]]

    testing_groups["Extra_test"] = testing_tests
    group_options["Extra_test"] = None

    # 2. Store to global variables
    GAMER_ABS_PATH = input_args["path"]
    gamer.gamer_abs_path = GAMER_ABS_PATH
    input_args["output"] += ".log"
    input_args["group_options"] = group_options

    # 3. Remove the existing log file
    if isfile( input_args["output"] ):
        print('WARNING!!! %s is already exist. The original log file will be removed.'%(input_args["output"]))
        os.remove( input_args["output"] )

    return testing_groups, input_args


def log_init( log_file_name ):
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

    ch           = logging.StreamHandler()
    file_handler = logging.FileHandler( log_file_name )

    # 2. Add log config into std output
    ch.setLevel(logging.DEBUG)
    ch.setFormatter( STD_FORMATTER )

    # 3. Add log config into file
    file_handler.setLevel(0)
    file_handler.setFormatter( SAVE_FORMATTER )

    return ch, file_handler


def set_up_logger( logger_name, ch, file_handler ):
    """
    Set up settings to logger object

    Parameters
    ----------

    logger_name  : string
       The name of logger.
    ch           : class logging.StreamHandler
       Saving the screen output format to the logger.
    file_handler : class logging.FileHandler
       Saving the file output format to the logger.

    Returns
    -------

    logger       : class logger.Logger
       The logger added the file handler and the stream handler with logger_name.

    """
    logger = logging.getLogger( logger_name )
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(ch)
    logger.addHandler(file_handler)

    return logger


def main( groups, ch, file_handler, **kwargs ):
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
    # Download compare list for tests
    gh_logger = set_up_logger( 'girder', ch, file_handler )
    #if gh.download_compare_version_list( logger=gh_logger ) != STATUS.SUCCESS:
    if gi.download_compare_version_list( GAMER_ABS_PATH, logger=gh_logger ) != STATUS.SUCCESS:
        raise BaseException("The download from girder fails.")

    # Loop over all groups
    group_status = { group_name:{"status":True, "reason":""} for group_name in groups }
    for group_name in groups:
        tests = groups[group_name]
        test_opts = kwargs["group_options"][group_name]
        test_classes = [ gamer.gamer_test( test_name, tests[test_name], GAMER_ABS_PATH, ch, file_handler ) for test_name in tests ]
        group_logger = set_up_logger( group_name, ch, file_handler )
        group_logger.info( 'Group %s start.' %(group_name) )
        for test in test_classes:
            test.logger.info( 'Test %s start.' %(test.name) )

            # 1. Set up gamer make configuration
            if test_opts != None: test.config += test_opts   # add the group option
            run_mpi = True  if "mpi=true" in test.config or "mpi" in test.config or kwargs["mpi"] else False

            # 2. Compile gamer
            os.chdir( GAMER_ABS_PATH + '/src' )
            if test.compile_gamer( **kwargs ) != STATUS.SUCCESS: continue

            # 3. Run gamer
            if test.run_all_inputs( run_mpi, **kwargs ) != STATUS.SUCCESS: continue

            # 4. Download compare file
            #if gh.download_test_compare_data( test.name, test.ref_path, logger=gh_logger ) != STATUS.SUCCESS:
            if gi.download_data( test.name, GAMER_ABS_PATH, test.ref_path, logger=gh_logger ) != STATUS.SUCCESS:
                raise BaseException("The download from girder fails.")

            # 5. Prepare analysis data (e.g. L1 error)
            if test.prepare_analysis( **kwargs ) != STATUS.SUCCESS: continue

            # 6. Compare the data
            # 6.1 Compare the Record__Note
            # It is not necessary to compare the Record__Note for now
            if test.compare_note( **kwargs ) != STATUS.SUCCESS: pass

            # 6.2 Prepare GAMER_comapre tool
            os.chdir( GAMER_ABS_PATH + '/tool/analysis/gamer_compare_data/' )
            if test.make_compare_tool( **kwargs ) != STATUS.SUCCESS: continue

            # 6.2 Compare data
            if test.compare_data( **kwargs ) != STATUS.SUCCESS: continue

            # 7. User analyze
            if test.user_analyze( **kwargs ) != STATUS.SUCCESS: continue

            test.logger.info('Test %s end.' %(test.name))

        # Record the test result
        for test in test_classes:
            if test.status == STATUS.SUCCESS: continue
            group_status[group_name]["status"] = False
            group_status[group_name]["reason"] += test.name + ", "
        group_status[group_name]["result"] = { test.name:{"status":test.status, "reason":test.reason} for test in test_classes }

        group_logger.info( 'Group %s end.' %(group_name) )

    return group_status


def write_args_to_log( logger, **kwargs ):
    logger.info("Record all arguments have been set.")
    for arg in kwargs:
       if arg == 'test':
           msg = " ".join([ TEST_INDEX[i] for i in kwargs[arg] ])
           logger.info("%-20s : %s"%("extra_test", msg))
       elif arg == 'group':
           msg = " ".join([ GROUP_INDEX[i] for i in kwargs[arg] ])
           logger.info("%-20s : %s"%(arg, msg))
       elif arg == "force_args":
           msg = " ".join(kwargs[arg])
           logger.info("%-20s : %s"%(arg, msg))
       elif arg == "group_options":
           continue
       elif type(kwargs[arg]) == type('str'):  # string
           logger.info("%-20s : %s"%(arg, kwargs[arg]))
       elif type(kwargs[arg]) == type(1):      # integer
           logger.info("%-20s : %d"%(arg, kwargs[arg]))
       elif type(kwargs[arg]) == type(1.):     # float
           logger.info("%-20s : %f"%(arg, kwargs[arg]))
       elif type(kwargs[arg]) == type(True):   # boolean
           logger.info("%-20s : %r"%(arg, kwargs[arg]))
       else:
           logger.info("Unknown type: %s"%(arg))
    return


def output_summary( result ):
    TEXT_RED   = "\033[91m"
    TEXT_GREEN = "\033[92m"
    TEXT_RESET = "\033[0m"
    print("========================================")
    print("Short summary: (Fail will be colored as red, passed will be colored as green.)")
    print("========================================")
    print("%-20s: %06s     %-15s  %06s  %s"%("Group name", "Passed", "Included tests", "Passed", "Reason"))
    fail_tests = {}
    summary = ""
    for key, val in result.items():
        summary += TEXT_GREEN if val["status"] else TEXT_RED
        summary += "%-20s: %06r     "%(key, val["status"])

        for sub_test, sub_result in val["result"].items():
            if summary[-1] == "\n":
                summary += "                                 "

            if sub_result["status"] == STATUS.SUCCESS:
                summary += TEXT_GREEN # Subtest Passed
            else:
                summary += TEXT_RED # Subtest Failed
                fail_tests[sub_test] = sub_result

            summary += "%-15s  %06r  %s\n"%(sub_test, sub_result["status"], sub_result["reason"])
    summary += TEXT_RESET
    print(summary)
    print("========================================")
    print("Please check <%s> for the detail message."%args["output"])

    return fail_tests


def upload_process(testing_groups, **kwargs):
    tests_to_upload = input("Enter tests you'd like to update result. ")
    tests_upload = tests_to_upload.split()

    run_test = {key for inner_dict in testing_groups.values() for key in inner_dict.keys()}
    reask = False
    for test_upload in tests_upload:
        if test_upload not in ALL_TESTS:
            print("'%s' no such test.")
            reask = True
        elif test_upload not in run_test:
            print("%s is not included in the tests you have ran.")
            reask = True
    if reask:
        upload_process(testing_groups, logger=kwargs['logger'])
        return

    for test in tests_upload:
        print("Uploading test %s" %test)
        test_folder = GAMER_ABS_PATH + '/regression_test/tests/' + test
        gi.upload_data(test, GAMER_ABS_PATH, test_folder, logger=kwargs['logger'])


####################################################################################################
# Main execution
####################################################################################################
if __name__ == '__main__':
    args, unknown_args = argument_handler()
    args = vars(args)

    # Initialize regression test
    testing_groups, args = reg_init( args )

    # Initialize logger
    ch, file_handler = log_init( args["output"] )

    test_logger = set_up_logger( 'regression_test', ch, file_handler )

    gamer_commit, reg_commit = get_git_info()

    test_logger.info( 'Recording the commit version.')
    test_logger.info( 'GAMER      version   : %-s'%(gamer_commit) )
    test_logger.info( 'Regression version   : %-s'%(reg_commit)   )

    write_args_to_log( test_logger, force_args=unknown_args, py_exe=sys.executable, **args )

    # Regression test
    try:
        test_logger.info('Regression test start.')
        result = main( testing_groups, ch, file_handler, force_args=unknown_args, py_exe=sys.executable, **args )
        #result = {"empty":{"status":True, "reason":"Pass"}}
        test_logger.info('Regression test done.')
    except Exception:
        test_logger.critical( '', exc_info=True )
        raise

    # Print out short summary
    fail_tests = output_summary(result)

    # Further process for fail tests
    # TODO: add further process such as do nothing or accept new result and upload to hub.yt
    if not fail_tests: exit(0)

    print("========================================")
    upload_or_not = input("Would you like to update new result for fail test? (Y/n)")
    if upload_or_not in ['Y','y','yes']:
        upload_logger = set_up_logger( 'upload', ch, file_handler )
        upload_process(testing_groups, logger=upload_logger)
    else:
        exit(1)
