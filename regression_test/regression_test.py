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
current_path         = os.getcwd()
gamer.gamer_abs_path = os.path.dirname(os.getcwd())

#2. Test problem
test_example_path = gamer.gamer_abs_path + '/regression_test/tests'
all_tests = {}
for direc in listdir( test_example_path ):
    if direc == 'Template':   continue
    all_tests[direc]=test_example_path + '/' + direc + '/Inputs'

test_index = [ t for t in all_tests ]   # Set up index of tests
        
#3. Logging variable
FILE_NAME      = 'test.log'    # The default name is 'test.log'
std_formatter  = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
save_formatter = logging.Formatter('%(levelname)-8s %(name)-15s %(message)s')
args           = {'error_level': 'level0'}



####################################################################################################
# Functions
####################################################################################################
def argument_handler():
    """
    Get the input arguements.
    """
    global FILE_NAME 
    testing_tests = {}
    test_groups = gamer.read_test_group()
    if len(sys.argv) > 1:
        for ind_arg in range(1,len(sys.argv)):
            if   '-error-level' in sys.argv[ind_arg]:
                args['error_level'] = sys.argv[ind_arg+1]
            elif '-p' in sys.argv[ind_arg] or '--path' in sys.argv[ind_arg]:
                gamer.abs_path = sys.argv[ind_arg+1]
            elif '-t' in sys.argv[ind_arg] or '--test' in sys.argv[ind_arg]:
                if sys.argv[ind_arg+1] in test_groups:
                    for test_name in test_groups[sys.argv[ind_arg+1]]:
                        testing_tests[test_name] = all_tests[test_name]
                    continue
                its = re.split(',',sys.argv[ind_arg+1])
                for ind in its:
                    testing_tests[test_index[int(ind)]]=all_tests[test_index[int(ind)]]
            elif '-o' in sys.argv[ind_arg] or '--output' in sys.argv[ind_arg]:
                FILE_NAME = sys.argv[ind_arg+1] + ".log"
            elif '-h' in sys.argv[ind_arg] or '--help' in sys.argv[ind_arg]:
                print('usage: python regression_test.py')
                print('Options:')
                print('\t-error_level\tError allows in this test."level0" or "level1". Default: "level0"')
                print('\t-p --path\tSet the path of gamer path.')
                print('\t-t --test\tSpecify tests to run. Tests should be saperated by "," Default: all tests')
                print('\t-o --output\tSet the file name of test log.')
                print('\t-h --help\tUsage and option list')
                print('Test index:')
                for i in range(len(test_index)):
                    print("\t%i\t%s"%(i,test_index[i]))
                print('Test groups:')
                for g in test_groups:
                    print('\t%s'%g)
                    for t in test_groups[g]:
                        print('\t\t%s'%t)
                quit()
#            else:
#                print('Unknow argument: %s' %sys.argv[ind_arg])
#                quit()
    
    if len(testing_tests) == 0:
        testing_tests = all_tests
    return testing_tests



def log_init():
    """
    Initialize the logger

    return
    ------
    ch           : stream handler
    file_handler : file handler
    """
    #1. Set up log config
    logging.basicConfig(level=0)
    
    ch           = logging.StreamHandler()
    file_handler = logging.FileHandler(FILE_NAME)

    #2. Add log config into std output
    ch.setLevel(logging.DEBUG)    
    ch.setFormatter(std_formatter)

    #3. Add log config into file
    file_handler.setLevel(0)
    file_handler.setFormatter(save_formatter)

    return ch, file_handler



def set_up_logger( logger, ch, file_handler ):
    """
    Set up settings to logger object

    Input
    -----
    logger       : logger class
    ch           : stream handler
    file_handler : file handler
    """
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(ch)
    logger.addHandler(file_handler)



def main( tests, ch , file_handler ):
    """
    Main regression test. 

    Input
    -----
    tests        : The problems need to be tested.
    ch           : stream handler
    file_handler : file handler
    """
    # Download compare list for tests
    gh_logger = logging.getLogger('girder')
    set_up_logger( gh_logger, ch, file_handler )
    gh.download_compare_version_list( logger=gh_logger )
    
    # Loop over all tests
    for test_name in tests:
        #1. Set up individual test logger
        indi_test_logger = logging.getLogger( test_name )
        set_up_logger( indi_test_logger, ch, file_handler )
        indi_test_logger.info( 'Test %s start' %(test_name) )

        #2. Set up gamer make configuration
        config_folder = gamer.gamer_abs_path + '/regression_test/tests/%s' %(test_name)
        config, input_settings = gamer.get_config(config_folder + '/configs')

        #3. Compile gamer
        indi_test_logger.info('Start compiling gamer')
        os.chdir(gamer.gamer_abs_path+'/src')
        Fail = gamer.make(config,logger=indi_test_logger)
        
        if Fail == 1:    continue       # Run next test if compilation failed.
    
        #4. Run gamer
        Fails = []
        test_folder = tests[test_name]
        #run gamer in different Input__Parameter    
        indi_test_logger.info('Start running test')
        for input_setting in input_settings:
            gamer.copy_example( test_folder, test_name +'_'+ input_setting )
            gamer.set_input( input_settings[input_setting] )
            Fail = gamer.run(logger=indi_test_logger,input_name=input_setting)

            if Fail == 1:    Fails.append(input_setting)

        #5. Analyze the result
        indi_test_logger.info('Start data analyze')
        gamer.analyze( test_name, Fails )
        #compare result and expect
        #download compare file
        gh.download_test_compare_data(test_name,config_folder,logger=gh_logger)
        
        #compare file
        os.chdir( gamer.gamer_abs_path+'/tool/analysis/gamer_compare_data/' )
        gamer.make_compare_tool( test_folder, config )

        indi_test_logger.info('Start Data_compare data consistency')
        gamer.check_answer( test_name, Fails, logger=indi_test_logger, error_level=args['error_level'] )
        #except Exception:
        #    test_logger.debug('Check script error')

        #except Exception:
        #    test_logger.error('Exception occurred', exc_info=True)
        #    pass
        indi_test_logger.info('Test %s end' %(test_name))



def test_result( all_tests ):
    """
    Check failure during tests
    
    Input
    -----
    all_tests: the test names have been done.
    """
    log_file = open('%s/%s'%(current_path, FILE_NAME))
    log = log_file.readlines()
    error_count = 0
    test_debug = { t:{} for t in all_tests }
    fail_test = {}
    
    for line in log:
        log_msg   = line.split()
        log_type  = log_msg[0]
        log_start = log_msg[2]

        if   log_type == 'INFO':
            if log_start != 'Start':    continue
            current_test  = log_msg[1]
            current_work  = log_msg[3]
            test_debug[current_test][current_work]=[]
        elif log_type == 'DEBUG':
            test_debug[current_test][current_work].append(line[25:])
        elif log_type == 'ERROR':
            if current_test == 'regression_test': continue
            if not current_test in fail_test:
                fail_test[current_test] = []
            fail_test[current_test].append(log_start)
        elif log_type == 'WARNING':
            if current_test == 'regression_test': continue
            if not current_test in fail_test:
                fail_test[current_test] = []
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
    testing_tests = argument_handler()
    
    # Remove the existing log file
    if isfile(FILE_NAME):
        print('%s is already exist. The original log file will be removed.'%(FILE_NAME))
        os.remove(FILE_NAME)

    ch, file_handler = log_init()

    test_logger = logging.getLogger('regression_test')
    set_up_logger( test_logger, ch, file_handler )

    try:
        test_logger.info('Test start.')
        main( testing_tests, ch, file_handler )
        test_logger.info('Test done.')
    except Exception:
        test_logger.critical('',exc_info=True)
        raise
    test_result(testing_tests)
