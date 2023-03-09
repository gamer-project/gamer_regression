from __future__ import print_function
import logging
import os
from os.path import isdir,isfile
import sys
import yaml
import six
import subprocess
import pandas as pd
import shutil as st
import numpy as np

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

from script.hdf5_file_config import hdf_info_read
from script.log_pipe import LogPipe



####################################################################################################
# Global variables
####################################################################################################
gamer_abs_path = '/work1/xuanshan/gamer'
config_path    = gamer_abs_path + '/regression_test/tests/AGORA_IsolatedGalaxy/configs'
analyze_path   = gamer_abs_path + '/regression_test/tests'
input_folder   = gamer_abs_path + '/example/test_problem/Hydro/'



####################################################################################################
# Functions
####################################################################################################
def get_config( config_path ):
    """
    Get the config of the test.

    Parameters
    ----------

    config_path: string
       The file path of the config.

    Returns
    -------

    data['MAKE_CONFIG']    : dict
       The config of the makefile.
    data['INPUT_SETTINGS'] : dict
       The config of the Input__Parameters.

    """
    with open(config_path) as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)
 
    return data['MAKE_CONFIG'], data['INPUT_SETTINGS']



def read_test_group():
    """
    Read the test group.

    Returns
    -------

    data :
       
    """
    with open('group') as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)
    return data
 


def generate_modify_command( config ):
    """
    Edit gamer configuration settings.

    Parameters
    ----------

    config :
        config of the options to be modified.

    Returns
    -------

    cmd :
        command
    """
    cmds = []
    
    #1. Enable HDF5 in all test
    cmds.append(['sed','-i','s/#SIMU_OPTION += -DSUPPORT_HDF5/SIMU_OPTION += -DSUPPORT_HDF5/g','Makefile'])
    
    #2. Enable options
    for enable_option in config['Enable']:
        cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_option,enable_option),'Makefile'])
    
    #3. Disable options
    for disable_option in config['Disable']:
        cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_option,disable_option),'Makefile'])

    #4. Generate variable modify command
    if 'Variable' in config:
        for var in config['Variable']:
            cmds.append(['sed','-i','s/%s/%s\t \#/g'%(var,var,config['Variable'][var])])
    
    return cmds



def make( config, **kwargs ):
    """
    Compliing GAMER.

    Parameters
    ----------

    config : dict
       The config of the makefile.
    kwargs :
       logger : class logger.Logger
          The logger of the test problem.

    Returns
    -------

    bool
       The status of the compilation.

    """
    try:
        out_log = LogPipe(kwargs['logger'],logging.DEBUG)
    except:
        exit("logger is not passed into %s."%(make.__name__) )

    #1. Back up and modify Makefile
    subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

    #2. get commands to modify Makefile.
    cmds = generate_modify_command(config)
    
    try:
        for cmd in cmds:
            subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print('Error in editing Makefile')
    mf = open('Makefile')

    #3. Compile GAMER
    try:
        subprocess.check_call(['make','clean'],stderr=out_log)
        subprocess.check_call(['make','-j'],stderr=out_log)
        #subprocess.check_call(['make -j > make.log'], stderr=out_log, shell=True)
    except subprocess.CalledProcessError:
        kwargs['logger'].error('Compiling error')
        return 1
    finally:
        out_log.close()

        #3.a Repair Makefile
        subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
        subprocess.check_call(['rm', 'Makefile.origin'])
        
        #3.b Check if compile successful
        if not isfile('./gamer'):
            kwargs['logger'].error('Compiling error')
            return 1

    return 0



def make_compare_tool( test_path, make_config, **kwargs ):
    """
    Make compare data program.

    Parameters
    ----------
    
    test_path   : string
       Directory of the test folder.
    make_config : dict
       Config of the makefile.
    kwargs :
       logger : class logger.Logger
          The logger of the test problem.
    
    Returns
    -------
    
    status: 0(success)/1(fail)
       The analysis is success or not.

    """
    status = 0
    try:
        logger = kwargs['logger']
    except:
        exit( "logger is not passed into %s."%(make_compare_tool.__name__) )
    
    cmds = []
    #1. Back up makefile
    subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

    #2. Check settings in configs
    for enable_config in make_config['Enable']:
        cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_config,enable_config),'Makefile'])
            
    for disable_config in make_config['Disable']:
        cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_config,disable_config),'Makefile'])
    
    #3. Modify makefile
    logger.info('Modifying the makefile.')
    try:
        for cmd in cmds:
            subprocess.check_call(cmd)
        logger.info('Modification complete.')
    except:
        logger.error('Error while modifying the compare tool makefile.')
        status = 1
    
    #4. Compile 
    logger.info('Compiling the compare tool.')
    try:
        subprocess.check_call(['make','clean'])
        subprocess.check_call(['make'])
        logger.info('Compilation complete.')
    except:
        logger.error('Error while compiling the compare tool.')
        status = 1
    
    #5. Repair makefile
    subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
    subprocess.check_call(['rm', 'Makefile.origin'])

    return status



def copy_example( file_folder, test_folder, **kwargs ):
    """
    Copy input files to work directory.

    Parameters
    ----------

    file_folder : string
       The folder which to be copied.
    test_folder : string
       The folder where running the test.
    kwargs:
       logger : class logger.Logger
          The logger of the test problem.
    
    Returns
    -------

    status      : 0(success)/1(fail)
       The copy is success or not.
    """
    status = 1
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(copy_example.__name__) )
    
    run_directory = gamer_abs_path + '/bin'
    
    logger.info('Copying the test folder: %s ---> %s'%(file_folder, run_directory+'/'+test_folder))
    try:
        if isdir(run_directory+'/'+test_folder):
            logger.warning('Test folder(%s) exist. ALL the original data will be removed.'%(run_directory+'/'+test_folder))
            logger.warning('If you changed `Input__Parameter` or `Input__TestProblem` before, those files will not be replaced.')
        else:
            os.chdir( run_directory )
            st.copytree( file_folder, test_folder )

        os.chdir( run_directory+'/'+test_folder )
        subprocess.check_call(['sh', 'clean.sh'])
        st.copy('../gamer','.')
        logger.info('Copy completed.')
        status = 0
    except:
        logger.error('Error on create work directory.')
    
    return status


def set_input( input_settings, **kwargs ):
    """
    Parameters
    ----------

    input_settings : dict
       The config of Input__Parameter.
    kwargs :
       logger : class logger.Logger
          The logger of the test problem.

    Returns
    -------

    status: 0(success)/1(fail)
       The setting is success or not.

    """
    status = 1
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(set_input.__name__) )
    
    cmds = []
    for input_file in input_settings:
        if input_settings[input_file] == None:
            continue
        
        #TODO: this should be a flixable option
        #Set gamer dump file as hdf5 file
        cmds.append(['sed','-i','s/OPT__OUTPUT_TOTAL/OPT__OUTPUT_TOTAL%14i #/g'%(1),input_file])
        
        #Set other input parameter
        for item in input_settings[input_file]:
            cmds.append(['sed','-i','s/%-29s/%-29s%-4s #/g'%(item,item,input_settings[input_file][item]),input_file])
    
    logger.info('Setting the Input__Parameter of test.')
    try:
       for cmd in cmds:
           subprocess.check_call(cmd)
       status = 0
       logger.info('Setting completed.')
    except:
       logger.error('Error on editing `Input__Parameter`.')

    return status



def run( **kwargs ):
    """
    Running GAMER.

    Parameters
    ----------

    kwargs :
       logger : class logger.Logger
          The logger of the test problem.


    Returns
    -------

    run_status: 0(success)/1(fail)
       The setting is success or not.

    """
    try:
        out_log = LogPipe( kwargs['logger'],logging.DEBUG )
    except:
        exit("logger is not passed into %s."%(run.__name__) )


    run_cmd = ['./gamer']
    if len(kwargs) != 0:  # prepare for the mpirun
        run_cmd = ["./gamer > log"]  #Store the simulation output under test directory
    
    #run gamer
    run_status = 0
    try:
        subprocess.check_call( run_cmd, stderr=out_log, shell=True )
        if not isfile('./Record__Note'):
            kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
            run_status = 1 

    except subprocess.CalledProcessError as err:        
        kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
        run_status = 1 

    finally:
        out_log.close()
    
    return run_status



def analyze( test_name, **kwargs ):
    """

    Parameters
    ----------

    test_name : string
        The name of the test.
    kwargs    :
       logger : class logger.Logger
          The logger of the test problem.

    Returns
    -------

    status    : 0(success)/1(fail)
       The analysis is success or not.
    """
    status = 1
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(analyze.__name__) )

    analyze_file = gamer_abs_path + '/regression_test/test/' + test_name + '/run_analyze.sh'
    
    if not isfile(analyze_file):    return # No need to analyze this test
    
    logger.info('Analyzing the data.')
    try:
        subprocess.check_call(['sh', analyze_file])
        logger.info('Analysis completed.')
        status = 0
    except subprocess.CalledProcessError:
        logger.error('%s has errors.'%(analyze_file))

    return status
        



def data_equal( result_file, expect_file, level='level0', data_type='HDF5', **kwargs ):
    """
    Parameters
    ----------

    result_file : string
       Directory of the test data.
    expect_file : string
       Directory of the reference data.
    level       : string ( level0 / level1 )
       The error level allowed.
    data_type   : string ( HDF5 / text )
       The data type of the compare files.
    kwargs      :
       logger : class logger.Logger
          The logger of the test problem.

    Returns
    -------

    fail_or_not : bool
       Fail the comparision or not.

    """
    try:
        logger  = kwargs['logger']
        
        # TODO: related to the step 2 in this function
        #out_log = LogPipe( logger, logging.DEBUG )
        #out_log.close()
    except:
        exit("logger is not passed into %s."%(data_equal.__name__) )
    
    try:
        error_allowed = kwargs['error_allowed']
    except:
        exit("error_allowed is not passed into %s."%(data_equal.__name__) )

    fail_or_not = False

    if data_type == 'HDF5':
        #1. Load result informations and expect informations
        compare_program = gamer_abs_path + '/tool/analysis/gamer_compare_data/GAMER_CompareData'
        compare_result  = gamer_abs_path + '/regression_test/compare_result'
        
        result_info = hdf_info_read(result_file)
        expect_info = hdf_info_read(expect_file)

        logger.info('Expect result is run from the version below.')
        logger.info('File name : %s' %expect_file)
        logger.info('Git Branch: %s' %expect_info.gitBranch)
        logger.info('Git Commit: %s' %expect_info.gitCommit)
        logger.info('Unique ID : %s' %expect_info.DataID)
        
        #2. Run data compare program
        subprocess.check_call([compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',error_allowed])
        
        # TODO: The following command still have bug to be solved.
        # compare_cmd = [ '%s -i %s -j %s -o %s -e %.5e > compare.log'%(compare_program, result_file, expect_file, \
        #                                                               compare_result, error_allowed) ]
        # subprocess.check_call( compare_cmd, stderr=out_log, shell=True )
        
        #3. Check if result equal to expect
        compare_file = open(compare_result)
        lines = compare_file.readlines()
        result_lines = []
        for line in lines:
            if line[0] == '#':    continue      # comment line
            result_lines.append(line)
        
        print(result_lines)
        if len(result_lines) > 4:    fail_or_not = True

    elif data_type == 'text':
        #1. Load result informations and expect informations
        a = pd.read_csv(result_file,header=0)
        b = pd.read_csv(expect_file,header=0)

        if a.shape != b.shape:
            fail_or_not = True
            logger.error('Data compare : data shapes are different.')
            return fail_or_not
            
        if   level == 'level0':
            fail_or_not = a.equals(b)
        elif level == 'level1':
            err = a - b
            if err > 6e-10:  # TODO: Replace to the wanted error
                fail_or_not = True
                logger.warning('Data_compare')
                logger.debug('Error is greater than expect')
        else:
            fail_or_not = True
            logger.error('Not suported error level: %s.'%(level))
    else:
        fail_or_not = True
        logger.error('Not supported data type: %s.'%(data_type))

    return fail_or_not



def error_comp( result_file, expect_file, **kwargs ):
    """
    Compare error from the reference file.

    Parameters
    ----------

    result_file : string
       Directory of the test data.
    expect_file : string
       Directory of the reference data.
    kwargs      :
       logger : class logger.Logger
          The logger of the test problem.

    Returns
    -------

    fail_or_not : bool
       Fail the comparision or not.
    """
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(error_comp.__name__) )
    
    a = pd.read_csv( result_file, delimiter=r'\s+', dtype={'Error':np.float64} )
    b = pd.read_csv( expect_file, delimiter=r'\s+', dtype={'Error':np.float64} )

    fail_or_not, greater = False, False

    if a.shape != b.shape: 
        fail_or_not = True
        logger.debug('Data compare : data shapes are different.')
        return fail_or_not
        
    comp = a > b
    for row in comp:
        for element in comp[row]:
            if element:
                greater = True
                break
        if greater:
            break
    
    if greater:
        fail_or_not = True
        logger.warning('Data_compare')
        logger.debug('Test Error is greater than expect.')

    return fail_or_not



def read_compare_list( test_name ):
    """
    
    Parameters
    ----------

    test_name : string
        The name of the test.

    Returns
    -------

    L1_err_compare  : dict
        Storing the data paths need to do the L1 error compare. 
    ident_data_comp : dict
        Storing the data paths need to compare as identical. 
    """
    L1_err_compare, ident_data_comp = {}, {}
    compare_list_file = analyze_path + '/' + test_name + '/' + 'compare_results'

    with open(compare_list_file) as stream:
        compare_list = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)

    if compare_list == None:    return L1_err_compare, ident_data_comp

    if 'compare' in compare_list:
        L1_err_compare = compare_list['compare']
    if 'identicle' in compare_list:
        ident_data_comp = compare_list['identicle']
    
    if L1_err_compare != {}:
        for item in L1_err_compare:
            L1_err_compare[item]['expect'] = gamer_abs_path + '/' + compare_list['compare'][item]['expect']
            L1_err_compare[item]['result'] = gamer_abs_path + '/' + compare_list['compare'][item]['result']
    if ident_data_comp != {}:
        for item in ident_data_comp:
            ident_data_comp[item]['expect'] = gamer_abs_path + '/' + compare_list['identicle'][item]['expect']
            ident_data_comp[item]['result'] = gamer_abs_path + '/' + compare_list['identicle'][item]['result']

    return L1_err_compare, ident_data_comp



def check_answer( test_name, fails, **kwargs ):
    """
    Check the answer of test result.

    Parameters
    ----------

    test_name : string
       Name of the test. 
    fails     : list
       List of the fail run.
    kwargs    : 
       logger : class logger.Logger
          The logger of the test problem.
       error_level : string
          The error allowed level.
    """
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(check_answer.__name__) )

    try:
        level = kwargs['error_level']
    except:
        exit("error_level is not passed into %s."%(check_answer.__name__) )

    #Get the list of files need to be compare
    err_comp_f, ident_comp_f = read_compare_list( test_name )

    #Start compare data files
    compare_fails = []
    if len(err_comp_f) > 0:
        for err_file in err_comp_f:
            if fails:    break

            result_file = err_comp_f[err_file]['result']
            expect_file = err_comp_f[err_file]['expect']

            if not isfile( result_file ):
                logger.error('No such error result file in the path.')
                break
            if not isfile( expect_file ):
                logger.error('No such error expect file in the path.')
                break

            fail_or_not = error_comp( result_file, expect_file, logger=logger )
            if fail_or_not:
                compare_fails.append([result_file,expect_file])
    
    identical_fails = []
    if len(ident_comp_f) > 0:
        for ident_file in ident_comp_f:
            f = False
            for fail in fails:
                if fail in ident_comp_f[ident_file]['result']:
                    f = True
                    break
            if f:
                continue
            
            result_file = ident_comp_f[ident_file]['result']
            expect_file = ident_comp_f[ident_file]['expect']

            if not isfile( result_file ):
                logger.error('No such result file in the path.')
                break
            if not isfile( expect_file ):
                logger.error('No such expect file in the path.')
                break
            
            fail_or_not = data_equal( result_file, expect_file, logger=logger, level=level, error_allowed=ident_comp_f[ident_file][level] )
            if fail_or_not:
                identical_fails.append([result_file,expect_file])

    #report the compare result in log 
    if len(identical_fails) > 0 or len(compare_fails) > 0:
        logger.warning('Data_compare')

    if len(identical_fails) > 0:
        logger.debug('Result data is not equal to expect data')
        for fail_files in identical_fails:
            result_info = hdf_info_read(fail_files[0])
            expect_info = hdf_info_read(fail_files[1])
            logger.debug('Expect result info:')
            logger.debug('File name : %s' %fail_files[1])
            logger.debug('Git Branch: %s' %expect_info.gitBranch)
            logger.debug('Git Commit: %s' %expect_info.gitCommit)
            logger.debug('Unique ID : %s' %expect_info.DataID)
            logger.debug('Test result info:')
            logger.debug('File name : %s' %fail_files[0])
            logger.debug('Git Branch: %s' %result_info.gitBranch)
            logger.debug('Git Commit: %s' %result_info.gitCommit)
            logger.debug('Unique ID : %s\n' %result_info.DataID)

    if len(compare_fails) > 0:
        logger.debug('Error compare result is greater than expect')



####################################################################################################
# Main execution 
####################################################################################################
if __name__ == '__main__':
    #setting logger for test
    test_logger = logging.getLogger('test')
    logging.basicConfig(level=0)
    ch = logging.StreamHandler()
    std_formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(std_formatter)
    test_logger.setLevel(logging.DEBUG)
    test_logger.propagate = False
    test_logger.addHandler(ch)

    config, input_settings = get_config(config_path)
    os.chdir('../src')
    Fail = make(config,logger=test_logger)
    print(Fail)
    #print(config)
    #print(input_settings)
    #read_compare_list('Riemann',{})
    #os.chdir('/work1/xuanshan/gamer/bin/Riemann')
    #for sets in input_settings:
    #    set_input(input_settings[sets])
#    make(config)
#    copy_example(input_folder)
#    run()
#    print check_answer([1],[1])
#    analyze('AcousticWave')
#    check_answer('AcousticWave',logger=test_logger)
    print('end')
