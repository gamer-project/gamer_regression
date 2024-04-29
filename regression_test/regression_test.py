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
# 1. Paths
CURRENT_ABS_PATH     = os.getcwd()
GAMER_ABS_PATH       = os.path.dirname( CURRENT_ABS_PATH )
gamer.gamer_abs_path = GAMER_ABS_PATH

# 2. Test problem
test_example_path = GAMER_ABS_PATH + '/regression_test/tests'
# get the config dict of each test
all_test_name = { direc:test_example_path+'/'+direc for direc in listdir(test_example_path) }
all_test_name.pop('Template')           # Remove the Template folder from test

ALL_TEST_CONFIGS, all_type_name = read_test_config( all_test_name )
NAME_INDEX = [ n for n in all_test_name ]
TYPE_INDEX = all_type_name

# 3. Logging variable
STD_FORMATTER  = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-20s : %(message)s')
SAVE_FORMATTER = logging.Formatter('%(levelname)-8s %(name)-20s %(message)s')

# 4. MPI variables
thread_nums     = os.cpu_count()
THREAD_PER_CORE = 2
CORE_PER_RANK   = 8
core_nums       = thread_nums // THREAD_PER_CORE
RANK_NUMS       = core_nums   // CORE_PER_RANK

# 5. Priorties
PRIOR = {"high":3, "medium":2, "low":1}



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

    test_msg = "Test type index:\n"
    test_msg += "".join( ["  %2d : %-20s\n"%(i, t) for i, t in enumerate(TYPE_INDEX)] )

    table = "%20s (id)"%("test name")
    for i in range(len(TYPE_INDEX)):
        table += " | %2d"%i
    table += "\n"
    for i, n in enumerate(NAME_INDEX):
        table += "%20s (%2d)"%(n, i)
        for j, t in enumerate(TYPE_INDEX):
            if n in ALL_TEST_CONFIGS:
                table += " | "
                if t in ALL_TEST_CONFIGS[n]:
                    table += "%2s"%(ALL_TEST_CONFIGS[n][t]["priority"][0].upper())
                else:
                    table += "  "
        table += "\n"

    parser = argparse.ArgumentParser( description = "Regression test of GAMER.",
                                      formatter_class = argparse.RawTextHelpFormatter,
                                      epilog = test_msg + table,
                                      allow_abbrev=False        # python version must be >= 3.5
                                      )

    parser.add_argument( "-e", "--error_level",
                         help="Error allowed in this test. \nDefault: %(default)s",
                         type=str, choices=["level0", "level1", "level2"],
                         default="level0"
                       )
    parser.add_argument( "-p", "--priority",
                         help="Priority of the regression test. \nDefault: %(default)s",
                         type=str, choices=[i for i in PRIOR],
                         default="high"
                       )
    parser.add_argument( "-n", "--name",
                         help="Specify the test name to run. \nDefault: %(default)s",
                         nargs="+",
                         type=int,
                         default=[]
                       )
    parser.add_argument( "-t", "--type",
                         help="Specify the test type to run. \nDefault: %(default)s",
                         nargs="+",
                         type=int,
                         default=[]
                       )
    parser.add_argument( "-o", "--output",
                         help="Set the file name of the test log. The output file will add a suffix '.log' automatically. \nDefault: %(default)s",
                         type=str,
                         default="test"
                       )

    parser.add_argument( "-m", "--machine",
                         help="Select the machine configuration in ../configs. \nDefault: %(default)s",
                         default="eureka_intel")

    # MPI arguments
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
    parser.add_argument( "--gpu_arch",
                         help="Specify the GPU architecture. \nDefault: %(default)s",
                         type=str,
                         default=get_gpu_arch()
                       )

    args, unknown = parser.parse_known_args()

    # Print out the unknown arguments
    if unknown != []: print("Simulation forced arguments or unknown arguments: ", unknown)

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
    # 0. Setting the default test type
    if len(input_args["type"]) == 0: input_args["type"] = [i for i in range(len(TYPE_INDEX))]
    if len(input_args["name"]) == 0: input_args["name"] = [i for i in range(len(NAME_INDEX))]

    # 1. Check if the input arguments are valid.
    for idx_g in input_args["type"]:
        if idx_g < 0 or idx_g > len(TYPE_INDEX):
            raise IndexError("Unrecognize index of the test type: %d"%idx_g)

    for idx_n in input_args["name"]:
        if idx_n < 0 or idx_n >= len(NAME_INDEX):
            raise IndexError("Unrecognize index of the test name: %d"%idx_n)

    test_configs = {}
    for idx_t in input_args["type"]:
        for idx_n in input_args["name"]:
            test_name = NAME_INDEX[idx_n]
            test_type = TYPE_INDEX[idx_t]
            try:
                test_priority = ALL_TEST_CONFIGS[test_name][test_type]["priority"]
                if PRIOR[test_priority] < PRIOR[input_args["priority"]]: continue
                test_configs[test_name+"_"+test_type] = ALL_TEST_CONFIGS[test_name][test_type]
                test_configs[test_name+"_"+test_type]["name"] = test_name
                test_configs[test_name+"_"+test_type]["type"] = test_type
            except:
                pass

    # 2. Store to global variables
    input_args["output"] += ".log"

    # 3. Remove the existing log file
    if isfile( input_args["output"] ):
        print('WARNING!!! %s is already exist. The original log file will be removed.'%(input_args["output"]))
        os.remove( input_args["output"] )

    return test_configs, input_args


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


def main( test_configs, ch, file_handler, **kwargs ):
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
    gh_logger = set_up_logger( 'girder', ch, file_handler )
    if gi.download_compare_version_list( GAMER_ABS_PATH, logger=gh_logger ) != STATUS.SUCCESS:
        raise BaseException("The download from girder fails.")

    tests = [ gamer.gamer_test( test_name, test_config, GAMER_ABS_PATH, ch, file_handler, kwargs["error_level"] ) for test_name, test_config in test_configs.items() ]
    for test in tests:
        continue
        test.logger.info( 'Test %s start.'%(test.name) )

        if test.run_all_cases( **kwargs )                             != STATUS.SUCCESS: continue
        if gi.download_data( test, GAMER_ABS_PATH, logger=gh_logger ) != STATUS.SUCCESS: continue
        if test.make_compare_tool( **kwargs )                         != STATUS.SUCCESS: continue
        if test.compare_data( **kwargs )                              != STATUS.SUCCESS: continue
        if test.execute_scripts( 'user_compare_script', **kwargs )    != STATUS.SUCCESS: continue

        test.logger.info( 'Test %s done.'%(test.name) )

    return {test.name:{"status":test.status, "reason":test.reason} for test in tests }


def write_args_to_log( logger, **kwargs ):
    logger.info("Record all arguments have been set.")
    for arg in kwargs:
       if arg == 'name':
           msg = " ".join([ NAME_INDEX[i] for i in kwargs[arg] ])
           logger.info("%-20s : %s"%("test name (name)", msg))
       elif arg == 'type':
           msg = " ".join([ TYPE_INDEX[i] for i in kwargs[arg] ])
           logger.info("%-20s : %s"%("test type (type)", msg))
       elif arg == "force_args":
           msg = " ".join(kwargs[arg])
           logger.info("%-20s : %s"%(arg, msg))
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
    SEP_LEN    = 50
    OUT_FORMAT = "%-20s: %-15s %s"
    print("="*SEP_LEN)
    print("Short summary: (Fail will be colored as red, passed will be colored as green.)")
    print("="*SEP_LEN)
    print(OUT_FORMAT%("Test name", "Error code", "Reason"))

    fail_tests = {}
    summary = ""
    for key, val in result.items():
        if val["status"] != STATUS.SUCCESS: fail_tests[key] = val["status"]
        summary += TEXT_GREEN if val["status"] == STATUS.SUCCESS else TEXT_RED
        summary += OUT_FORMAT%(key, STATUS.CODE_TABLE[val["status"]], val["reason"])
        summary += TEXT_RESET
        summary += "\n"

    print(summary, end="")
    print("="*SEP_LEN)
    print("Please check <%s> for the detailed message."%args["output"])

    return fail_tests


def upload_process( test_configs, **kwargs ):
    tests_to_upload = input("Enter tests you'd like to update result. ")
    tests_upload = tests_to_upload.split()

    reask = False
    for test_upload in tests_upload:
        if test_upload not in ALL_TEST_CONFIGS:
            print("'%s' no such test.")
            reask = True
        elif test_upload not in test_configs:
            print("%s is not included in the tests you have ran.")
            reask = True
    if reask:
        upload_process( test_configs, logger=kwargs['logger'] )
        return

    for test in tests_upload:
        print("Uploading test %s" %test)
        test_folder = GAMER_ABS_PATH + '/regression_test/tests/' + test
        gi.upload_data( test, GAMER_ABS_PATH, test_folder, logger=kwargs['logger'] )

    return


####################################################################################################
# Main execution
####################################################################################################
if __name__ == '__main__':
    args, unknown_args = argument_handler()
    args = vars(args)

    # Initialize regression test
    test_configs, args = reg_init( args )

    # Initialize logger
    ch, file_handler = log_init( args["output"] )

    test_logger = set_up_logger( 'regression_test', ch, file_handler )

    gamer_commit, reg_commit = get_git_info()

    test_logger.info( 'Recording the commit version.')
    test_logger.info( 'GAMER      version   : %-s'%(gamer_commit) )
    test_logger.info( 'Regression version   : %-s'%(reg_commit)   )

    write_args_to_log( test_logger, force_args=unknown_args, py_exe=sys.executable, **args )

    test_logger.info( 'Test to be run       : %-s'%(" ".join([ name for name in test_configs])) )

    # Regression test
    try:
        test_logger.info('Regression test start.')
        result = main( test_configs, ch, file_handler, force_args=unknown_args, py_exe=sys.executable, **args )
        test_logger.info('Regression test done.')
    except Exception:
        test_logger.critical( '', exc_info=True )
        raise

    # Print out short summary
    fail_tests = output_summary(result)

    # Further process for fail tests
    # TODO: add further process such as do nothing or accept new result and upload to hub.yt
    if fail_tests == {}: exit(0)

    print("========================================")
    upload_or_not = input("Would you like to update new result for fail test? (Y/n)")
    if upload_or_not in ['Y','y','yes']:
        upload_logger = set_up_logger( 'upload', ch, file_handler )
        upload_process( test_configs, logger=upload_logger )
    else:
        exit(1)
