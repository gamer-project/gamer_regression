from __future__ import print_function
import logging
import os
from os.path import isdir,isfile
import sys
import yaml
import six
import subprocess
import pandas as pd
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
RETURN_SUCCESS = 0
RETURN_FAIL    = 1



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



def generate_modify_command( config, **kwargs ):
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
    # initialize the single test mpi status
    kwargs["mpi_test"] = False

    cmd = [kwargs["py_exe"], "configure.py"]
    # 0. machine configuration
    cmd.append("--machine="+kwargs["machine"])

    # 1. simulation and miscellaneous options
    cmd.append("--hdf5=True")  # Enable HDF5 in all test
    for option in config:
        if "=" in option:
            cmd.append("--"+option)
        else:
            cmd.append("--"+option+"=True")

    # 2. parallel options
    if kwargs['mpi']:    cmd.append("--mpi=True")
    cmd.append("--gpu_arch="+kwargs["gpu_arch"])

    # 3. user force enable options
    for arg in kwargs["force_args"]:
        cmd.append(arg)

    return cmd



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
        logger  = kwargs['logger']
        out_log = LogPipe(logger, logging.DEBUG)
    except:
        raise BaseException("logger is not passed into %s."%(make.__name__) )

    #1. Back up and modify Makefile
    subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

    #2. get commands to modify Makefile.
    cmd = generate_modify_command( config, **kwargs )

    try:
        logger.debug("Generating Makefile using: %s"%(" ".join(cmd)))
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        logger.error('Error while editing Makefile')
        subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
        subprocess.check_call(['rm', 'Makefile.origin'])
        out_log.close()
        return RETURN_FAIL

    #3. Compile GAMER
    try:
        subprocess.check_call( ['make','clean'], stderr=out_log )
        if kwargs["hide_make"]:
            subprocess.check_call( ['make -j > make.log'], stderr=out_log, shell=True )
            subprocess.check_call( ['rm', 'make.log'] )
        else:
            subprocess.check_call( ['make','-j'], stderr=out_log )

    except subprocess.CalledProcessError:
        logger.error('Compiling error')
        return RETURN_FAIL

    finally:
        # Repair Makefile
        subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
        subprocess.check_call(['rm', 'Makefile.origin'])

        out_log.close()

    # 4. Check if gamer exist
    if not isfile('./gamer'):
        logger.error('GAMER not exist')
        return RETURN_FAIL

    return RETURN_SUCCESS



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
    status = RETURN_SUCCESS
    try:
        logger = kwargs['logger']
        out_log = LogPipe(logger, logging.DEBUG)
    except:
        raise BaseException( "logger is not passed into %s."%(make_compare_tool.__name__) )

    cmds = []
    #1. Back up makefile
    subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

    #2. Check settings in configs
    #TODO: This part is hard coded cause we use the configure.py to generate the Makefile, but it does not support for the compare tool
    if "model=HYDRO" in make_config:
        cmds.append(['sed','-i','s/SIMU_OPTION += -DMODEL=HYDRO/SIMU_OPTION += -DMODEL=HYDRO/g','Makefile'])
    if "model=ELBDM" in make_config:
        cmds.append(['sed','-i','s/SIMU_OPTION += -DMODEL=HYDRO/SIMU_OPTION += -DMODEL=ELBDM/g','Makefile'])
    if "double" in make_config:
        cmds.append(['sed','-i','s/#SIMU_OPTION += -DFLOAT8/SIMU_OPTION += -DFLOAT8/g','Makefile'])
    if "debug" in make_config:
        cmds.append(['sed','-i','s/SIMU_OPTION += -DGAMER_DEBUG/SIMU_OPTION += -DMODEL=GAMER_DEBUG/g','Makefile'])
    if "hdf5" in make_config:
        cmds.append(['sed','-i','s/SIMU_OPTION += -DSUPPORT_HDF5/SIMU_OPTION += -DSUPPORT_HDF5/g','Makefile'])

    #cmds.append(['sed','-i','s/#SIMU_OPTION += -DFLOAT8/SIMU_OPTION += -DFLOAT8/g','Makefile'])
    cmds.append(['sed','-i','s/SIMU_OPTION += -DSUPPORT_HDF5/SIMU_OPTION += -DSUPPORT_HDF5/g','Makefile'])

    #3. Modify makefile
    logger.info('Modifying the makefile.')
    try:
        for cmd in cmds:
            subprocess.check_call(cmd)
        logger.info('Modification complete.')
    except:
        logger.error('Error while modifying the compare tool makefile.')
        subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
        subprocess.check_call(['rm', 'Makefile.origin'])
        out_log.close()
        return RETURN_FAIL

    #4. Compile
    logger.info('Compiling the compare tool.')
    try:
        subprocess.check_call( ['make','clean'], stderr=out_log )

        if kwargs["hide_make"]:
            subprocess.check_call( ['make > make.log'], stderr=out_log, shell=True )
            subprocess.check_call( ['rm', 'make.log'], stderr=out_log )
        else:
            subprocess.check_call( ['make'], stderr=out_log )
        logger.info('Compilation complete.')

    except:
        logger.error('Error while compiling the compare tool.')
        status = RETURN_FAIL
    finally:
        # Repair makefile
        subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
        subprocess.check_call(['rm', 'Makefile.origin'])

        out_log.close()

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
    status = RETURN_SUCCESS
    try:
        logger = kwargs['logger']
    except:
        raise BaseException("logger is not passed into %s."%(copy_example.__name__) )

    run_directory = gamer_abs_path + '/bin'

    logger.info('Copying the test folder: %s ---> %s'%(file_folder, run_directory+'/'+test_folder))
    try:
        os.chdir( run_directory )

        if isdir(run_directory+'/'+test_folder):
            logger.warning('Test folder(%s) exist. ALL the original data will be removed.'%(run_directory+'/'+test_folder))
        else:
            subprocess.check_call(['cp', '-r', file_folder, test_folder])

        os.chdir( run_directory+'/'+test_folder )
        subprocess.check_call(['sh', 'clean.sh'])
        subprocess.check_call(['cp', '../gamer', '.'])
        logger.info('Copy completed.')
    except:
        status = RETURN_FAIL
        logger.error('Error when createing running directory.')

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
    status = RETURN_SUCCESS
    try:
        logger = kwargs['logger']
    except:
        raise BaseException("logger is not passed into %s."%(set_input.__name__) )

    cmds = []
    for input_file in input_settings:
        if input_settings[input_file] == None:
            continue

        #TODO: this should be a flixable option
        #Set gamer dump file as hdf5 file
        cmds.append(['sed','-i','s/OPT__OUTPUT_TOTAL/OPT__OUTPUT_TOTAL%14i #/g'%(1),input_file])
        #cmds.append(['sed','-i', r's/(OPT__OUTPUT_TOTAL[\s+])([^\s+])/<1>%d #/g'%(1),input_file])

        #Set other input parameter
        for item in input_settings[input_file]:
            cmds.append(['sed','-i','s/%-29s/%-29s%-4s #/g'%(item,item,input_settings[input_file][item]),input_file])
            #cmds.append(['sed','-i', 's/(%s[\s+])([^\s])/<1>%s #/g'%(item,input_settings[input_file][item]),input_file])

    logger.info('Setting the Input__Parameter of test.')
    try:
       for cmd in cmds:
           subprocess.check_call(cmd)
       logger.info('Setting completed.')
    except:
       status = RETURN_FAIL
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
        raise BaseException("logger is not passed into %s."%(run.__name__) )

    #Store the simulation output under test directory
    run_cmd = ["./gamer 1>>log 2>&1"]
    if kwargs["mpi_test"]:
        run_cmd = ['mpirun -map-by ppr:%d:socket:pe=%d --report-bindings ./gamer 1>>log 2>&1'%(kwargs["mpi_rank"], kwargs["mpi_core_per_rank"])]

    #run gamer
    run_status = RETURN_SUCCESS
    try:
        subprocess.check_call( run_cmd, stderr=out_log, shell=True )

    except subprocess.CalledProcessError as err:
        kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
        run_status = RETURN_FAIL

    finally:
        out_log.close()

    if not isfile('./Record__Note'):
        kwargs['logger'].error('No Record__Note in %s'%(kwargs['input_name']))
        run_status = RETURN_FAIL

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
    status = RETURN_SUCCESS
    try:
        logger = kwargs['logger']
    except:
        raise BaseException("logger is not passed into %s."%(analyze.__name__) )

    analyze_file = gamer_abs_path + '/regression_test/test/' + test_name + '/run_analyze.sh'

    if not isfile(analyze_file):    return RETURN_SUCCESS # No need to analyze this test

    logger.info('Analyzing the data.')
    try:
        subprocess.check_call(['sh', analyze_file])
        logger.info('Analysis completed.')
    except subprocess.CalledProcessError:
        status = RETURN_FAIL
        logger.error('%s has errors.'%(analyze_file))

    return status



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
    compare_list_file = gamer_abs_path + '/regression_test/tests/' + test_name + '/' + 'compare_results'

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



def compare_data( test_name, **kwargs ):
    """
    Check the answer of test result.

    Parameters
    ----------

    test_name : string
       Name of the test.
    kwargs    :
       logger : class logger.Logger
          The logger of the test problem.
       error_level : string
          The error allowed level.
    """
    try:
        logger = kwargs['logger']
    except:
        raise BaseException("logger is not passed into %s."%(check_answer.__name__) )

    try:
        level = kwargs['error_level']
    except:
        raise BaseException("error_level is not passed into %s."%(check_answer.__name__) )

    #Get the list of files need to be compare
    err_comp_f, ident_comp_f = read_compare_list( test_name )

    #Start compare data files
    compare_fails = []
    if len(err_comp_f) > 0:
        for err_file in err_comp_f:
            result_file = err_comp_f[err_file]['result']
            expect_file = err_comp_f[err_file]['expect']
            #print("error: ",  err_comp_f[err_file][level], err_file, level)

            if not isfile( result_file ):
                logger.error('No such result file in the path: %s'%result_file)
                return RETURN_FAIL

            if not isfile( expect_file ):
                logger.error('No such expect file in the path: %s'%expect_file)
                return RETURN_FAIL

            logger.info('Comparing error: %s <-> %s'%(result_file, expect_file))
            if compare_error( result_file, expect_file, logger=logger ):
                compare_fails.append([result_file,expect_file])
            logger.info('Comparing error complete.')

    identical_fails = []
    if len(ident_comp_f) > 0:
        for ident_file in ident_comp_f:
            result_file = ident_comp_f[ident_file]['result']
            expect_file = ident_comp_f[ident_file]['expect']
            #print("ident: ",  ident_comp_f[ident_file][level], ident_file, level)

            if not isfile( result_file ):
                logger.error('No such result file in the path: %s'%result_file)
                return RETURN_FAIL

            if not isfile( expect_file ):
                logger.error('No such expect file in the path: %s'%expect_file)
                return RETURN_FAIL

            logger.info('Comparing equal: %s <-> %s'%(result_file, expect_file))
            if compare_identical( result_file, expect_file, logger=logger, error_allowed=ident_comp_f[ident_file][level] ):
                identical_fails.append([result_file,expect_file])
            logger.info('Comparing equal complete.')

    # report the compare result in log
    if len(identical_fails) > 0:
        logger.debug('Data_identical')
        logger.debug('Result data is not equal to expect data')
        for fail_files in identical_fails:
            result_info = hdf_info_read(fail_files[0])
            expect_info = hdf_info_read(fail_files[1])
            str_len = str(max( len(fail_files[0]), len(fail_files[1]), 50 ))
            str_format = "%-"+str_len+"s %-"+str_len+"s"
            logger.debug( 'Type      : '+str_format%("Expect",              "Result") )
            logger.debug( 'File name : '+str_format%(fail_files[1],         fail_files[0])         )
            logger.debug( 'Git Branch: '+str_format%(expect_info.gitBranch, result_info.gitBranch) )
            logger.debug( 'Git Commit: '+str_format%(expect_info.gitCommit, result_info.gitCommit) )
            logger.debug( 'Unique ID : '+str_format%(expect_info.DataID,    result_info.DataID)    )

    if len(compare_fails) > 0:
        logger.debug('Data_compare')
        logger.debug('Error compare result is greater than expect')

    if len(identical_fails) > 0 or len(compare_fails) > 0:
        return RETURN_FAIL

    return RETURN_SUCCESS



def compare_identical( result_file, expect_file, data_type='HDF5', **kwargs ):
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
        out_log = LogPipe( logger, logging.DEBUG )
    except:
        raise BaseException("logger is not passed into %s."%(data_equal.__name__) )

    try:
        error_allowed = kwargs['error_allowed']
    except:
        raise BaseException("error_allowed is not passed into %s."%(data_equal.__name__) )

    fail_or_not = False

    #TODO: data_type is not able yet.
    if data_type == 'HDF5':
        #1. Load result informations and expect informations
        compare_program = gamer_abs_path + '/tool/analysis/gamer_compare_data/GAMER_CompareData'
        compare_result  = gamer_abs_path + '/regression_test/compare_result'

        result_info = hdf_info_read(result_file)
        expect_info = hdf_info_read(expect_file)

        #2. Run data compare program
        try:
            with open('compare.log', 'a') as out_file:
                subprocess.check_call( [compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',error_allowed,'-c'],
                                       stderr=out_log, stdout=out_file)
        except:
            subprocess.check_call( ['rm', 'compare.log'] )
            logger.error("Error while compiling files.")
            fail_or_not = True
        finally:
            out_log.close()

        if fail_or_not: return fail_or_not

        logger.info('Expect result is run from the version below.')
        logger.info('File name : %s' %expect_file)
        logger.info('Git Branch: %s' %expect_info.gitBranch)
        logger.info('Git Commit: %s' %expect_info.gitCommit)
        logger.info('Unique ID : %s' %expect_info.DataID)

        #3. Check if result equal to expect
        with open( compare_result, 'r' ) as f:
            lines = f.readlines()
            for line in lines:
                if line[0] in ['#', '\n']:    continue      # comment and empty line
                fail_or_not = True
                break

    elif data_type == 'text':
    #TODO: this function is not correct yet.
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
            err = np.abs(a - b)
            if err > error_allowed:
                fail_or_not = True
                logger.warning('Data_compare')
                logger.debug('Error is greater than expect. Expected: %.4e. Test: %.4e.'%(error_allowed, err))
        else:
            fail_or_not = True
            logger.error('Not suported error level: %s.'%(level))
    else:
        fail_or_not = True
        logger.error('Not supported data type: %s.'%(data_type))

    return fail_or_not



def compare_error( result_file, expect_file, **kwargs ):
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
        raise BaseException("logger is not passed into %s."%(error_comp.__name__) )

    a = pd.read_csv( result_file, delimiter=r'\s+', dtype={'Error':np.float64} )
    b = pd.read_csv( expect_file, delimiter=r'\s+', dtype={'Error':np.float64} )

    fail_or_not, greater = False, False

    if a.shape != b.shape:
        fail_or_not = True
        logger.error('Data compare : data shapes are different.')
        return fail_or_not

    # print out the errors and store to log
    for key in a:
        if key == "NGrid":
            logger.debug("%-5s: %16s %16s"%("NGrid", "result err", "expect err"))
            continue
        for j in range(a.shape[0]):
            if a[key][j] > b[key][j]:
                greater = True
                logger.debug("%-5d: %+16e %+16e => Unaccepted error!"%(a["NGrid"][j], a[key][j], b[key][j]))
            else:
                logger.debug("%-5d: %+16e %+16e"%(a["NGrid"][j], a[key][j], b[key][j]))

    if greater:
        fail_or_not = True
        logger.warning('Data_compare')
        logger.debug('Test Error is greater than expect.')

    return fail_or_not



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

    config_path    = gamer_abs_path + '/regression_test/tests/AGORA_IsolatedGalaxy/configs'
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
    input_folder   = gamer_abs_path + '/example/test_problem/Hydro/'
#    copy_example(input_folder)
#    run()
#    print check_answer([1],[1])
#    analyze('AcousticWave')
#    check_answer('AcousticWave',logger=test_logger)
    print('end')
