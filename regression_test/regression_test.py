from __future__ import print_function
import argparse
import os
import sys
import re
import logging
import logging.config
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
#1. Paths
CURRENT_ABS_PATH     = os.getcwd()
GAMER_ABS_PATH       = os.path.dirname( CURRENT_ABS_PATH )
gamer.gamer_abs_path = GAMER_ABS_PATH

#2. Test problem
test_example_path = GAMER_ABS_PATH + '/regression_test/tests'
ALL_TESTS = {}
for direc in listdir( test_example_path ):
    if direc == 'Template':   continue
    ALL_TESTS[direc]=test_example_path + '/' + direc + '/Inputs'

TEST_INDEX = [ t for t in ALL_TESTS ]   # Set up index of tests
        
#3. Logging variable
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

    args : class argparse.Namespace
       Storing the input arguments.

    """
    test_groups = gamer.read_test_group()

    test_msg = ""
    test_msg += "Test index:\n"
    for i in range(len(TEST_INDEX)):
        test_msg += "\t%i\t%s\n"%(i,TEST_INDEX[i])
    test_msg += "Test groups:\n"
    for g in test_groups:
        test_msg += "\t%s\n"%g
        for t in test_groups[g]:
            test_msg += "\t\t%s\n"%t
    
    parser = argparse.ArgumentParser( description = "Regression test of GAMER.", 
                                      formatter_class = argparse.RawTextHelpFormatter,
                                      epilog = test_msg )

    parser.add_argument( "--error-level",
                         help="Error allowed in this test. (level0/level1) \nDefault: %(default)s",
                         type=str,
                         default="level0"
                       )
    parser.add_argument( "-p", "--path", 
                         help="Set the path of the GAMER path. \nDefault: %(default)s", 
                         type=str, 
                         default=GAMER_ABS_PATH
                       )
    parser.add_argument( "-t", "--test", 
                         help="Specify tests to run. \nDefault: %(default)s", 
                         nargs="+",
                         type=int, 
                         default=[ i for i in range(len(ALL_TESTS))]
                       )
    parser.add_argument( "-o", "--output", 
                         help="Set the file name of the test log. The output file will add a suffix '.log' automatically. \nDefault: %(default)s", 
                         type=str, 
                         default="test"
                       )
    
    # OPENMP
    parser.add_argument( "--OPENMP",
                         help="Enable to use OpenMP. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )

    # MPI arguments
    parser.add_argument( "--MPI",
                         help="Enable to use open-mpi. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )
    parser.add_argument( "--path_mpi",
                         help="Specify the path of the open-mpi compiler. \nDefault: %(default)s",
                         type=str,
                         default="/software/openmpi/default"
                       )

    # GPU arguments
    parser.add_argument( "--GPU",
                         help="Enable to use GPU. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )
    parser.add_argument( "--GPU-arch",
                         help="Specify the gpu architecture. \nDefault: %(default)s",
                         type=str,
                         default="TURING"
                       )
    parser.add_argument( "--path_nvcc",
                         help="Specify the path of the nvcc compiler. \nDefault: %(default)s",
                         type=str,
                         default="/software/cuda/default"
                       )
    
    # Others
    parser.add_argument( "--HIDE_MAKE",
                         help="Hide the make messages. \nDefault: %(default)s",
                         action="store_true",
                         default=False
                       )

    args, unknown = parser.parse_known_args()

    # Print out the unknown arguments and invalid test index
    if unknown != []:
        print("Unknown arguments: ", unknown)
    
    return args



def reg_init( input_args ):
    """
    testing_test : list
       A list contains strings of test name which to be tested.
    """
    global GAMER_ABS_PATH
   
    testing_tests = {}
    # 2. Check if the input arguments are valid.
    for idx in input_args.test:
        if idx >= len(TEST_INDEX) or idx < 0:
            print("Unrecognize index of the test: %d"%idx)
            continue
        testing_tests[TEST_INDEX[idx]] = ALL_TESTS[TEST_INDEX[idx]]

    #2.b Unsupported arguments
    if not input_args.OPENMP:
        print("Disable OPENMP option is not supported yet. Reset to true.")
        input_args.OPENMP = True
    
    if input_args.MPI:
        print("MPI option is not supported yet. Reset to false.")
        input_args.MPI = False
    if input_args.path_mpi != "/software/openmpi/default":
        print("path_mpi option is not supported yet. This option is not functional now.")
    
    if input_args.GPU:
        print("GPU option is not supported yet. Reset to false.")
        input_args.GPU = False
    if input_args.GPU_arch != "TURING":
        print("GPU_arch option is not supported yet. This option is not functional now.")
    if input_args.path_nvcc != "/software/cuda/default":
        print("path_nvcc option is not supported yet. This option is not functional now.")


    # 3. Store to global variables
    GAMER_ABS_PATH = input_args.path
    gamer.gamer_abs_path = GAMER_ABS_PATH
    input_args.output += ".log"
   
   # Remove the existing log file
    if isfile( input_args.output ):
        print('WARNING!!! %s is already exist. The original log file will be removed.'%(input_args.output))
        os.remove( input_args.output )

    return testing_tests, input_args



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



def main( tests, ch, file_handler, **kwargs ):
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
    Fail = gh.download_compare_version_list( logger=gh_logger )
    #TODO: stop the program if download is fail
    
    # Loop over all tests
    for test_name in tests:
        #1. Set up individual test logger
        indi_test_logger = set_up_logger( test_name, ch, file_handler )
        indi_test_logger.info( 'Test %s start.' %(test_name) )

        #2. Set up gamer make configuration
        config_folder = GAMER_ABS_PATH + '/regression_test/tests/' + test_name
        config, input_settings = gamer.get_config( config_folder + '/configs' )

        #3. Compile gamer
        indi_test_logger.info('Start compiling gamer')
        os.chdir( GAMER_ABS_PATH + '/src' )
        Fail = gamer.make( config, logger=indi_test_logger, **kwargs )
        
        if Fail == 1:    continue       # Run next test if compilation failed.
    
        #4. Run gamer
        Fails = []
        test_folder = tests[test_name]
        #run gamer in different Input__Parameter    
        indi_test_logger.info('Start running test.')
        for input_setting in input_settings:
            Fail = gamer.copy_example( test_folder, test_name+'_'+ input_setting, logger=indi_test_logger, **kwargs )
            #TODO: stop the test if file copy fail

            Fail = gamer.set_input( input_settings[input_setting], logger=indi_test_logger, **kwargs )
            #TODO: stop the test if file setting fail

            Fail = gamer.run( logger=indi_test_logger, input_name=input_setting, **kwargs )
            #TODO: stop the test if execution fail

            if Fail == 1:    Fails.append(input_setting)

        #5. Analyze the result
        indi_test_logger.info('Start data analyze.')
        Fail = gamer.analyze( test_name, logger=indi_test_logger ) #TODO: the analysis script has a lot of problem
        #TODO: stop the test if execution fail

        #compare result and expect
        #download compare file
        Fail = gh.download_test_compare_data( test_name, config_folder, logger=gh_logger )
        #TODO: stop the program if download fail
        
        #compare file
        os.chdir( GAMER_ABS_PATH + '/tool/analysis/gamer_compare_data/' )
        indi_test_logger.info('Start compiling compare tool.')
        Fail = gamer.make_compare_tool( test_folder, config, logger=indi_test_logger, **kwargs )
        #TODO: stop the test if compilation fail.

        indi_test_logger.info('Start Data_compare data consistency.')
        #gamer.check_answer( test_name, Fails, logger=indi_test_logger, error_level=kwargs['error_level'] )
        gamer.check_answer( test_name, Fails, logger=indi_test_logger, **kwargs )
        #except Exception:
        #    test_logger.debug('Check script error')

        #except Exception:
        #    test_logger.error('Exception occurred', exc_info=True)
        #    pass
        indi_test_logger.info('Test %s end.' %(test_name))



def write_args_to_log( logger, **kwargs ):
    logger.info("Record all arguments have been set.")
    for arg in kwargs:
       if arg == 'test':
           msg = ""
           for i in kwargs[arg]: 
               msg += TEST_INDEX[i] + " "
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



def test_result( all_tests, input_args ):
    """
    Check failure during tests.
    
    Parameters
    ----------

    all_tests: dict 
       A dictionary of a sequence of the test paths with a key access of the test names.
    """
    log_file = open('%s/%s'%(CURRENT_ABS_PATH, input_args.output))
    log = log_file.readlines()
    error_count = 0
    test_debug   = { t:{} for t in all_tests }  # storing the DEBUG message
    test_warning = { t:{} for t in all_tests }  # storing the WARNING message 
    fail_test = {}
    
    for line in log:
        log_msg   = line.split()
        log_type  = log_msg[0]

        if   log_type == 'INFO':
            log_start = log_msg[2]
            if log_start != 'Start':    continue
            current_test = log_msg[1]
            current_work = log_msg[3]
            test_debug[current_test][current_work]=[]
            test_warning[current_test][current_work]=[]
        elif log_type == 'DEBUG':
            test_debug[current_test][current_work].append(line[25:])
        elif log_type == 'WARNING':
            test_warning[current_test][current_work].append(line[25:])
        elif log_type == 'ERROR':
            if current_test == 'regression_test': continue
            if not current_test in fail_test:
                fail_test[current_test] = []
            log_start = log_msg[2]
            fail_test[current_test].append(log_start)
        else:
            print('Unrecognized log type. log_type = %s'%(log_type))
    
    #summary test results
    print('\nTest Result: ')
    
    for test in all_tests:
        if test in fail_test:
            print('%-20s : Failed'%(test))
            for fail_stage in fail_test[test]:
                print('\tFail stage:')
                print('\t\t%s'%fail_stage)
                print('\tError message:')
                for errorline in test_debug[test][fail_stage]:
                    print('\t\t%s'%errorline)

        else:
            print('%-20s : Passed'%(test))
    
    print('(%i/%i) test(s) fail.'%(len(fail_test),len(all_tests)))
    if len(fail_test) == 0:    print('Regression test passed!')
    
    if len(fail_test) > 0:
        exit(1)



def ask_for_compare_file_update():
    #1. ask for the test to update
    #2. update those tests and version list file
    return 0



####################################################################################################
# Main execution 
####################################################################################################
if __name__ == '__main__':
    args = argument_handler()
    
    # Initialize regression test
    testing_tests, args = reg_init( args )

    # Initialize logger 
    ch, file_handler = log_init( args.output )

    test_logger = set_up_logger( 'regression_test', ch, file_handler )
    
    write_args_to_log( test_logger, **vars(args) )
 
    # Regression test
    try:
        test_logger.info('Regression test start.')
        main( testing_tests, ch, file_handler, **vars(args) )
        test_logger.info('Regression test done.')
    except Exception:
        test_logger.critical( '', exc_info=True )
        raise
    
    # print the test result
    test_result( testing_tests, args )
