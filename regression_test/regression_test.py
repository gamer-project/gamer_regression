from __future__ import print_function
import argparse
import os
import sys
import ctypes
import logging
import logging.config
import subprocess
from os import listdir
from os.path import isfile, isdir, join

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

import script.girder_handler as gh
import script.run_gamer as gamer



####################################################################################################
# Global variables
####################################################################################################
# 0. Variables
STATUS_SUCCESS = 0
STATUS_FAIL    = 1

# 1. Paths
CURRENT_ABS_PATH     = os.getcwd()
GAMER_ABS_PATH       = os.path.dirname( CURRENT_ABS_PATH )
gamer.gamer_abs_path = GAMER_ABS_PATH

# 2. Test problem
test_example_path = GAMER_ABS_PATH + '/regression_test/tests'
ALL_TESTS = { direc:test_example_path+'/'+direc+'/Inputs' for direc in listdir(test_example_path) }
ALL_TESTS.pop('Template')                 # Remove the Template folder from test
ALL_GROUPS = gamer.read_test_group()

TEST_INDEX  = [ t for t in ALL_TESTS  ]   # Set up index of tests
GROUP_INDEX = [ g for g in ALL_GROUPS ]   # Set up index of groups


# 3. Logging variable
STD_FORMATTER  = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
SAVE_FORMATTER = logging.Formatter('%(levelname)-8s %(name)-15s %(message)s')



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

    test_msg = "Test index:\n"
    test_msg += "".join( ["  %2d : %-20s\n"%(i, t) for i, t in enumerate(TEST_INDEX)] )
    test_msg += "Test groups:\n"
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
                         type=str, choices=["level0", "level1"],
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
                         default=2
                       )
    parser.add_argument( "--mpi_core_per_rank", metavar="N_CORE",
                         help="Core used per rank. \nDefault: %(default)s",
                         default=8
                       )

    # GPU arguments
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
    if unknown != []:
        print("Simulation forced or unknown arguments: ", unknown)

    return args, unknown



def get_gpu_arch():
    """
    Outputs some information on CUDA-enabled devices on your computer, including current memory usage.

    It's a port of https://gist.github.com/f0k/0d6431e3faa60bffc788f8b4daa029b1
    from C to Python with ctypes, so it can run without compiling anything. Note
    that this is a direct translation with no attempt to make the code Pythonic.
    It's meant as a general demonstration on how to obtain CUDA device information
    from Python without resorting to nvidia-smi or a compiled Python extension.

    Author: Jan Schluter
    License: MIT (https://gist.github.com/f0k/63a664160d016a491b2cbea15913d549#gistcomment-3870498)
    """
    CUDA_SUCCESS = 0
    libnames = ('libcuda.so', 'libcuda.dylib', 'cuda.dll')
    for libname in libnames:
        try:
            cuda = ctypes.CDLL(libname)
        except OSError:
            continue
        else:
            break
    else:
        raise OSError("could not load any of: " + ' '.join(libnames))

    nGpus, cc_major, cc_minor, device = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int()

    def cuda_check_error( result ):
        if result == CUDA_SUCCESS: return

        error_str = ctypes.c_char_p()

        cuda.cuGetErrorString(result, ctypes.byref(error_str))
        raise BaseException("CUDA failed with error code %d: %s" % (result, error_str.value.decode()))

        return

    cuda_check_error( cuda.cuInit(0) )
    cuda_check_error( cuda.cuDeviceGetCount(ctypes.byref(nGpus)) )

    arch = ""
    if nGpus.value > 1: print("WARNING: More than one GPU. Selecting the last GPU architecture.")
    for i in range(nGpus.value):
        cuda_check_error( cuda.cuDeviceGet(ctypes.byref(device), i) )
        cuda_check_error( cuda.cuDeviceComputeCapability(ctypes.byref(cc_major), ctypes.byref(cc_minor), device) )

        # https://en.wikipedia.org/wiki/CUDA#GPUs_supported
        if cc_major.value == 1:
            arch = "TESLA"
        elif cc_major.value == 2:
            arch = "FERMI"
        elif cc_major.value == 3:
            arch = "KEPLER"
        elif cc_major.value == 5:
            arch = "MAXWELL"
        elif cc_major.value == 6:
            arch = "PASCAL"
        elif cc_major.value == 7 and cc_minor.value in [0, 2]:
            arch = "VOLTA"
        elif cc_major.value == 7 and cc_minor.value == 5:
            arch = "TURING"
        elif cc_major.value == 8 and cc_minor.value in [0, 6, 7]:
            arch = "AMPERE"
        elif cc_major.value == 8 and cc_minor.value == 9:
            arch = "ADA"
        elif cc_major.value == 9 and cc_minor.value == 0:
            arch = "HOPPER"
        else:
            raise BaseException("Undefined architecture in the script.")

    return arch


def get_git_info():
    """
    Returns
    -------

       gamer_commit      : gamer commit hash
       regression_commit : regression commit hash
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
    testing_test : list
       A list contains strings of test name which to be tested.
    """
    global GAMER_ABS_PATH

    testing_groups = {}
    group_options  = {}
    # 0. Setting the default
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
    #1. Set up log config
    logging.basicConfig(level=0)

    ch           = logging.StreamHandler()
    file_handler = logging.FileHandler( log_file_name )

    #2. Add log config into std output
    ch.setLevel(logging.DEBUG)
    ch.setFormatter( STD_FORMATTER )

    #3. Add log config into file
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
    if gh.download_compare_version_list( logger=gh_logger ) == STATUS_FAIL:
        raise BaseException("The download from girder fails.")

    # Loop over all groups
    group_status = { group_name:{"status":True, "reason":""} for group_name in groups }
    for group_name in groups:
        tests = groups[group_name]
        test_opts = kwargs["group_options"][group_name]
        test_status = { test_name:{"status":True, "reason":""} for test_name in tests }
        group_logger = set_up_logger( group_name, ch, file_handler )
        group_logger.info( 'Group %s start.' %(group_name) )
        for test_name in tests:
            #1. Set up individual test logger
            indi_test_logger = set_up_logger( test_name, ch, file_handler )
            indi_test_logger.info( 'Test %s start.' %(test_name) )

            #2. Set up gamer make configuration
            config_folder = GAMER_ABS_PATH + '/regression_test/tests/' + test_name
            config, input_settings = gamer.get_config( config_folder + '/configs' )
            if test_opts != None: config += test_opts   # add the group option
            run_mpi = True  if "mpi=true" in config or "mpi" in config or kwargs["mpi"]  else False

            #3. Compile gamer
            indi_test_logger.info('Start compiling gamer')
            os.chdir( GAMER_ABS_PATH + '/src' )
            if gamer.make( config, logger=indi_test_logger, **kwargs ) == STATUS_FAIL:
                test_status[test_name]["status"] = False
                test_status[test_name]["reason"] = "Compiling error."
                group_status[group_name]["status"] = False
                group_status[group_name]["reason"] += test_name + ", "
                continue

            #4. Run gamer
            indi_test_logger.info('Start running test.')
            test_folder = tests[test_name]
            for input_setting in input_settings:    # run gamer with different Input__Parameter
                if gamer.copy_example( test_folder, test_name+'_'+str(input_setting), logger=indi_test_logger, **kwargs ) == STATUS_FAIL:
                    test_status[test_name]["status"] = False
                    test_status[test_name]["reason"] = "Copying error of %s."%input_setting
                    group_status[group_name]["status"] = False
                    group_status[group_name]["reason"] += test_name + ", "
                    continue

                if gamer.set_input( input_settings[input_setting], logger=indi_test_logger, **kwargs ) == STATUS_FAIL:
                    test_status[test_name]["status"] = False
                    test_status[test_name]["reason"] = "Setting error of %s."%input_setting
                    group_status[group_name]["status"] = False
                    group_status[group_name]["reason"] += test_name + ", "
                    continue

                if gamer.run( mpi_test=run_mpi, logger=indi_test_logger, input_name=input_setting, **kwargs ) == STATUS_FAIL:
                    test_status[test_name]["status"] = False
                    test_status[test_name]["reason"] = "Running error of %s."%input_setting
                    group_status[group_name]["status"] = False
                    group_status[group_name]["reason"] += test_name + ", "
                    continue

            if not test_status[test_name]["status"]:    continue    # Run next test if any of the subtest fail.

            #5. Prepare analysis data (e.g. L1 error)
            #download compare file
            if gh.download_test_compare_data( test_name, config_folder, logger=gh_logger ) == STATUS_FAIL:
                raise BaseException("The download from girder fails.")

            indi_test_logger.info('Start preparing data.')
            if gamer.prepare_analysis( test_name, logger=indi_test_logger ) == STATUS_FAIL:
                test_status[test_name]["status"] = False
                test_status[test_name]["reason"] = "Preparing analysis data error."
                group_status[group_name]["status"] = False
                group_status[group_name]["reason"] += test_name + ", "
                continue

            #5. Compare by the GAMER_comapre tool
            #compare file
            os.chdir( GAMER_ABS_PATH + '/tool/analysis/gamer_compare_data/' )
            indi_test_logger.info('Start compiling compare tool.')
            if gamer.make_compare_tool( test_folder, config, logger=indi_test_logger, **kwargs ) == STATUS_FAIL:
                test_status[test_name]["status"] = False
                test_status[test_name]["reason"] = "Compiling error of compare tool."
                group_status[group_name]["status"] = False
                group_status[group_name]["reason"] += test_name + ", "
                continue

            indi_test_logger.info('Start Data_compare data consistency.')
            if gamer.compare_data( test_name, logger=indi_test_logger, **kwargs ) == STATUS_FAIL:
                test_status[test_name]["status"] = False
                test_status[test_name]["reason"] = "Comparing fail."
                group_status[group_name]["status"] = False
                group_status[group_name]["reason"] += test_name + ", "
                continue

            #6. User analyze
            indi_test_logger.info('Start user analyze.')
            if gamer.user_analyze( test_name, logger=indi_test_logger ) == STATUS_FAIL:
                test_status[test_name]["status"] = False
                test_status[test_name]["reason"] = "Analyzing error."
                group_status[group_name]["status"] = False
                group_status[group_name]["reason"] += test_name + ", "
                continue


            indi_test_logger.info('Test %s end.' %(test_name))
        group_status[group_name]["result"] = test_status
        group_logger.info( 'Group %s end.' %(group_name) )

    return group_status



def write_args_to_log( logger, **kwargs ):
    logger.info("Record all arguments have been set.")
    for arg in kwargs:
       if arg == 'test':
           msg = ""
           for i in kwargs[arg]:
               msg += TEST_INDEX[i] + " "
           logger.info("%-20s : %s"%("extra_test", msg))
       elif arg == 'group':
           msg = ""
           for i in kwargs[arg]:
               msg += GROUP_INDEX[i] + " "
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
        test_logger.info('Regression test done.')
    except Exception:
        test_logger.critical( '', exc_info=True )
        raise

    print("========================================")
    print("Short summary: (Fail will be colored as red, passed will be colored as green.)")
    print("========================================")
    print("%-20s: %06s     %-s"%("Group name", "Passed", "Fail tests"))
    for key, val in result.items():
        if not val["status"]:
            print("\033[91m" + "%-20s: %06r     %-s"%(key, val["status"], val["reason"]) + "\033[0m")
        else:
            print("\033[92m" + "%-20s: %06r     %-s"%(key, val["status"], val["reason"]) + "\033[0m")
    print("========================================")

    #print("%-20s: %06s     %-s"%("Test problem", "Passed", "Fail reason"))
    #for key, val in result.items():
    #    print("%-20s: %06r     %-s"%(key, val["status"], val["reason"]))
    #print("========================================")
    print("Please check <%s> for the detail message."%args["output"])

