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
import copy

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

from script.hdf5_file_config import hdf_info_read
from script.log_pipe import LogPipe
from script.utilities import check_dict_key, read_yaml



####################################################################################################
# Global variables
####################################################################################################
gamer_abs_path = '/work1/xuanshan/gamer'
STATUS_SUCCESS = 0
STATUS_FAIL    = 1



####################################################################################################
# Classes
####################################################################################################
class gamer_test():
    def __init__( self, name, folder, gamer_abs_path, ch, file_handler ):
        self.name = name
        self.folder = folder
        self.ref_path = gamer_abs_path + '/regression_test/tests/' + name
        self.status = True
        self.reason = ""
        self.config, self.inputs = read_yaml( self.ref_path + '/configs', 'config' )

        self.logger = logging.getLogger( name )
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.logger.addHandler(ch)
        self.logger.addHandler(file_handler)
        return

    def compile_gamer( self, **kwargs ):
        out_log = LogPipe( self.logger, logging.DEBUG )

        # 1. Back up the original Makefile
        keep_makefile = isfile('Makefile')
        if keep_makefile: subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

        # 2. Get commands to modify Makefile.
        cmd = generate_modify_command( self.config, **kwargs )

        try:
            self.logger.debug("Generating Makefile using: %s"%(" ".join(cmd)))
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError:
            self.set_fail_test("Error while editing Makefile.")
            subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
            subprocess.check_call(['rm', 'Makefile.origin'])
            out_log.close()
            return STATUS_FAIL

        # 3. Compile GAMER
        try:
            subprocess.check_call( ['make','clean'], stderr=out_log )
            if kwargs["hide_make"]:
                subprocess.check_call( ['make -j > make.log'], stderr=out_log, shell=True )
                subprocess.check_call( ['rm', 'make.log'] )
            else:
                subprocess.check_call( ['make','-j'], stderr=out_log )

        except subprocess.CalledProcessError:
            self.set_fail_test("Compiling error.")
            return STATUS_FAIL

        finally:
            # Repair Makefile
            if keep_makefile:
                subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
                subprocess.check_call(['rm', 'Makefile.origin'])
            else:
                subprocess.check_call(['rm', 'Makefile'])

            out_log.close()

        # 4. Check if gamer exist
        if not isfile('./gamer'):
            self.set_fail_test("GAMER does not exist.")
            return STATUS_FAIL

        return STATUS_SUCCESS

    def run_all_inputs( self, run_mpi, **kwargs ):
        for input_setting in self.inputs:
            if copy_example( self.folder, self.name+'_'+str(input_setting), logger=self.logger, **kwargs ) == STATUS_FAIL:
                self.set_fail_test("Copying error of %s."%input_setting)
                return STATUS_FAIL

            if set_input( self.inputs[input_setting], logger=self.logger, **kwargs ) == STATUS_FAIL:
                self.set_fail_test("Setting error of %s."%input_setting)
                return STATUS_FAIL

            if run( mpi_test=run_mpi, logger=self.logger, input_name=input_setting, **kwargs ) == STATUS_FAIL:
                self.set_fail_test("Running error of %s."%input_setting)
                return STATUS_FAIL

        return STATUS_SUCCESS

    def prepare_analysis( self, **kwargs ):
        """

        Parameters
        ----------

        Returns
        -------

        status    : 0(success)/1(fail)
           The analysis is success or not.
        """
        status = STATUS_SUCCESS

        analyze_filename = 'prepare_analyze_data.sh'
        analyze_script   = self.ref_path + '/' + analyze_filename

        if not isfile(analyze_script):    return STATUS_SUCCESS # No need to analyze this test

        try:
            subprocess.check_call(['sh', analyze_script, gamer_abs_path])
            self.logger.info('Prepare analysis data completed.')
        except subprocess.CalledProcessError:
            status = STATUS_FAIL
            self.set_fail_test( '%s has errors. (In %s)'%(analyze_script, prepare_analysis.__name__) )

        return status

    def make_compare_tool( self, **kwargs ):
        """
        Make compare data program.

        Parameters
        ----------

        Returns
        -------

        status: 0(success)/1(fail)
           The analysis is success or not.

        """
        status  = STATUS_SUCCESS
        out_log = LogPipe(self.logger, logging.DEBUG)

        cmds = []
        # 1. Back up makefile
        os.rename('Makefile','Makefile.origin')
        with open('Makefile.origin') as f:
            makefile_content = f.read()

        # 2. Check settings in configs
        #TODO: This part is hard coded cause we use the configure.py to generate the Makefile, but it does not support for the compare tool

        if "model=HYDRO" in self.config:
            makefile_content = makefile_content.replace("SIMU_OPTION += -DMODEL=HYDRO", "SIMU_OPTION += -DMODEL=HYDRO")
        if "model=ELBDM" in self.config:
            makefile_content = makefile_content.replace("SIMU_OPTION += -DMODEL=HYDRO", "SIMU_OPTION += -DMODEL=ELBDM")
        if "double" in self.config:
            makefile_content = makefile_content.replace("#SIMU_OPTION += -DFLOAT8", "SIMU_OPTION += -DFLOAT8")
        if "debug" in self.config:
            makefile_content = makefile_content.replace("#SIMU_OPTION += -DGAMER_DEBUG", "SIMU_OPTION += -DGAME_DEBUG")
        if "hdf5" in self.config:
            makefile_content = makefile_content.replace("#SIMU_OPTION += -DSUPPORT_HDF5", "SIMU_OPTION += -DSUPPORT_HDF5")

        #makefile_content = makefile_content.replace('#SIMU_OPTION += -DFLOAT8','SIMU_OPTION += -DFLOAT8')
        makefile_content = makefile_content.replace("#SIMU_OPTION += -DSUPPORT_HDF5", "SIMU_OPTION += -DSUPPORT_HDF5")

        # 3. Modify makefile
        self.logger.info('Modifying the makefile.')
        with open('Makefile','w') as f:
            f.write(makefile_content)
        self.logger.info('Modification complete.')

        # 4. Compile
        self.logger.info('Compiling the compare tool.')
        try:
            subprocess.check_call( ['make','clean'], stderr=out_log )

            if kwargs["hide_make"]:
                subprocess.check_call( ['make > make.log'], stderr=out_log, shell=True )
                os.remove('make.log')
            else:
                subprocess.check_call( ['make'], stderr=out_log )
            self.logger.info('Compilation complete.')

        except:
            self.set_fail_test('Error while compiling the compare tool.')
            status = STATUS_FAIL
        finally:
            # Repair makefile
            os.remove('Makefile')
            os.rename('Makefile.origin','Makefile')

            out_log.close()

        return status

    def compare_data( self, **kwargs ):
        """
        Check the answer of test result.

        Parameters
        ----------

        kwargs    :
           error_level : string
              The error allowed level.
        """
        check_dict_key( 'error_level', kwargs, "kwargs" )
        level  = kwargs['error_level']

        #Get the list of files need to be compare
        err_comp_f, ident_comp_f = read_compare_list( self.name )

        #Start compare data files
        compare_fails = []
        if len(err_comp_f) > 0:
            for err_file in err_comp_f:
                check_dict_key( ['result', 'expect', 'level0'], err_comp_f[err_file], "err_comp_f[err_file]" )
                result_file = err_comp_f[err_file]['result']
                expect_file = err_comp_f[err_file]['expect']

                if not isfile( result_file ):
                    self.set_fail_test('Result file (%s) does not exist.'%result_file)
                    return STATUS_FAIL

                if not isfile( expect_file ):
                    self.set_fail_test('Expect file (%s) does not exist.'%expect_file)
                    return STATUS_FAIL

                self.logger.info('Comparing L1 error: %s <-> %s'%(result_file, expect_file))

                if level not in err_comp_f[err_file]:
                    self.logger.warning( "Error tolerance of %s is not set. Switch to level0!"%(level, err_file) )
                    error_allowed = err_comp_f[err_file]['level0']
                else:
                    error_allowed = err_comp_f[err_file][level]

                if compare_error( result_file, expect_file, error_allowed=error_allowed, logger=self.logger ):
                    compare_fails.append([result_file,expect_file])
                self.logger.info('Comparing L1 error complete.')

        identical_fails = []
        if len(ident_comp_f) > 0:
            for ident_file in ident_comp_f:
                check_dict_key( ['result', 'expect', 'f_type', 'level0'], ident_comp_f[ident_file], "ident_comp_f[ident_file]" )
                result_file = ident_comp_f[ident_file]['result']
                expect_file = ident_comp_f[ident_file]['expect']
                file_type   = ident_comp_f[ident_file]['f_type']

                if not isfile( result_file ):
                    self.set_fail_test('Result file (%s) does not exist.'%result_file)
                    return STATUS_FAIL

                if not isfile( expect_file ):
                    self.set_fail_test('Expect file (%s) does not exist.'%expect_file)
                    return STATUS_FAIL

                self.logger.info('Comparing identical: %s <-> %s'%(result_file, expect_file))

                if level not in ident_comp_f[ident_file]:
                    self.logger.warning( "Error tolerance of %s is not set. Switch to level0!"%(level, ident_file) )
                    error_allowed = ident_comp_f[ident_file]['level0']
                else:
                    error_allowed = ident_comp_f[ident_file][level]

                if compare_identical( result_file, expect_file, data_type=file_type, logger=self.logger, error_allowed=error_allowed ):
                    identical_fails.append( [result_file, expect_file, file_type] )
                self.logger.info('Comparing identical complete.')

        if len(identical_fails) > 0 or len(compare_fails) > 0:
            self.set_fail_test('Comparing to reference data fail.')
            return STATUS_FAIL

        return STATUS_SUCCESS

    def compare_note( self, **kwargs ):
        """
        Compare the Record__Note files
        """
        for input_setting in self.inputs:
            run_dir     = self.name + "_" + str(input_setting)
            result_note = gamer_abs_path + "/bin/" + run_dir + "/Record__Note"
            expect_note = gamer_abs_path + "/regression_test/tests/" + self.name + "/" + run_dir + "/Record__Note"

            #TODO: replace the logger.error to the set_fail_test if comparing Record_Note is necessary
            if not isfile( result_note ):
                self.logger.error( "Result Record__Note (%s) is not exist!"%result_note )
                return STATUS_FAIL

            if not isfile( expect_note ):
                self.logger.error( "Expect Record__Note (%s) is not exist!"%expect_note )
                return STATUS_FAIL

            self.logger.info( "Comparing Record__Note: %s <-> %s"%(result_note, expect_note) )

            para_result = store_note_para( result_note )
            para_expect = store_note_para( expect_note )
            diff_para   = compare_para( para_result, para_expect )

            self.logger.debug("%-30s | %40s | %40s |"%("Parameter name", "result parameter", "expect parameter"))
            for key in diff_para["1"]:
                self.logger.debug("%-30s | %40s | %40s |"%(key, diff_para["1"][key], diff_para["2"][key]))
            self.logger.info("Comparison of Record__Note done.")

        return STATUS_SUCCESS

    def user_analyze( self, **kwargs ):
        #TODO: this function is very similar to prepare_analysis. We should combine them
        status = STATUS_SUCCESS

        analyze_filename = 'user_analyze.sh'
        analyze_script   = self.ref_path + '/' + analyze_filename

        if not isfile(analyze_script):    return STATUS_SUCCESS # No need to analyze this test

        try:
            subprocess.check_call(['sh', analyze_script, gamer_abs_path])
            self.logger.info('User analysis completed.')
        except subprocess.CalledProcessError:
            status = STATUS_FAIL
            self.set_fail_test('%s has errors. (In %s)'%(analyze_script, user_analyze.__name__))

        return status

    def set_fail_test( self, reason ):
        self.status = False
        self.reason = reason
        self.logger.error( reason )
        return


####################################################################################################
# Functions
####################################################################################################
def store_note_para( file_name ):
    with open( file_name, "r" ) as f:
        data = f.readlines()

    paras = {}
    in_section = False
    cur_sec = ""
    section_pattern = "*****"
    skip_sec = ["Flag Criterion (# of Particles per Patch)", "Flag Criterion (Lohner Error Estimator)", "Cell Size and Scale (scale = number of cells at the finest level)", "Compilation Time", "Current Time"]
    end_sec  = ["OpenMP Diagnosis", "Device Diagnosis"]
    for i in range(len(data)):
        if data[i] == "\n": continue        # ignore the empty line

        # ignore the section split line, and change the section
        if section_pattern in data[i]:
            in_section = not in_section
            continue

        # record the section name
        if not in_section:
            sec = data[i].rstrip()
            cur_sec = sec
            if cur_sec in end_sec: break   # End of the parameter information
            paras[cur_sec] = {}
            continue

        if cur_sec in skip_sec: continue   # Skip the parameter information

        para = data[i].rstrip().split()
        key = " ".join(para[0:-1])
        paras[cur_sec][key] = para[-1]
    return paras


def compare_para( para_1, para_2 ):
    para_1_copy = copy.deepcopy( para_1 )
    para_2_copy = copy.deepcopy( para_2 )

    diff_para = {"1":{}, "2":{}}
    for sec in para_1:
        # 1. store all the sections exist only in para_1
        if sec not in para_2:
            for para in para_1[sec]:
                diff_para["1"][para] = para_1[sec][para]
                diff_para["2"][para] = "EMPTY"
            continue
        # 2. store all the parameters exist only in para_1
        for para in para_1[sec]:
            if para not in para_2[sec]:
                diff_para["1"][para] = para_1[sec][para]
                diff_para["2"][para] = "EMPTY"
                para_1_copy[sec].pop(para)
                continue

            # 3. store the different parameter
            if para_1[sec][para] != para_2[sec][para]:
                diff_para["1"][para] = para_1[sec][para]
                diff_para["2"][para] = para_2[sec][para]

            # 4. remove the compared parameter
            para_1_copy[sec].pop(para)
            para_2_copy[sec].pop(para)

        # 5. store all the parameters exist only in para_2
        for para in para_2_copy[sec]:
            diff_para["1"][para] = "EMPTY"
            diff_para["2"][para] = para_2[sec][para]

        # 6. clean empty dict
        para_1_copy.pop(sec)
        para_2_copy.pop(sec)

    # 7. store all the sections exist only in para_2
    for sec in para_2:
        if sec in para_1: continue
        for para in para_2_copy[sec]:
            diff_para["1"][para] = "EMPTY"
            diff_para["2"][para] = para_2[sec][para]
        para_2_copy.pop(sec)

    return diff_para


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

    # 3. gpu options
    if kwargs['gpu']:    cmd.append("--gpu=True")
    cmd.append("--gpu_arch="+kwargs["gpu_arch"])

    # 4. user force enable options
    for arg in kwargs["force_args"]:
        cmd.append(arg)

    return cmd


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
    check_dict_key( 'logger', kwargs, "kwargs" )

    status = STATUS_SUCCESS
    logger = kwargs['logger']

    run_directory = gamer_abs_path + '/bin'

    logger.info('Copying the test folder: %s ---> %s'%(file_folder, run_directory+'/'+test_folder))
    try:
        os.chdir( run_directory )

        if isdir(run_directory+'/'+test_folder):
            logger.warning('Test folder (%s) exist. ALL the original data (including Input__* and your scripts) will be removed.'%(run_directory+'/'+test_folder))
            subprocess.check_call(['rm', '-rf', run_directory+'/'+test_folder])

        subprocess.check_call(['cp', '-r', file_folder, test_folder])
        os.chdir( run_directory+'/'+test_folder )
        subprocess.check_call(['sh', 'clean.sh'])
        subprocess.check_call(['cp', '../gamer', '.'])
        logger.info('Copy completed.')
    except:
        status = STATUS_FAIL
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
    check_dict_key( 'logger', kwargs, "kwargs" )

    status = STATUS_SUCCESS
    logger = kwargs['logger']

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
        status = STATUS_FAIL
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
    check_dict_key( 'logger', kwargs, "kwargs" )

    logger  = kwargs['logger']
    out_log = LogPipe( logger, logging.DEBUG )

    #Store the simulation output under test directory
    run_cmd = ["./gamer 1>>log 2>&1"]
    if kwargs["mpi_test"]:
        run_cmd = ['mpirun -map-by ppr:%d:socket:pe=%d --report-bindings ./gamer 1>>log 2>&1'%(kwargs["mpi_rank"], kwargs["mpi_core_per_rank"])]

    #run gamer
    run_status = STATUS_SUCCESS
    try:
        logger.info('Running GAMER.')
        subprocess.check_call( run_cmd, stderr=out_log, shell=True )
        logger.info('GAMER OVER.')

    except subprocess.CalledProcessError as err:
        kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
        run_status = STATUS_FAIL

    finally:
        out_log.close()

    if not isfile('./Record__Note'):
        kwargs['logger'].error('No Record__Note in %s'%(kwargs['input_name']))
        run_status = STATUS_FAIL

    return run_status


def prepare_analysis( test_name, **kwargs ):
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
    check_dict_key( 'logger', kwargs, "kwargs" )

    status = STATUS_SUCCESS
    logger = kwargs['logger']

    analyze_script = 'prepare_analyze_data.sh'
    analyze_file   = self.ref_path + '/' + analyze_script

    if not isfile(analyze_file):    return STATUS_SUCCESS # No need to analyze this test

    try:
        subprocess.check_call(['sh', analyze_file, gamer_abs_path])
        logger.info('Prepare analysis data completed.')
    except subprocess.CalledProcessError:
        status = STATUS_FAIL
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
    compare_list      = read_yaml( compare_list_file, "compare_list" )

    if compare_list == None:    return L1_err_compare, ident_data_comp

    if 'compare' in compare_list:
        L1_err_compare = compare_list['compare']
    if 'identical' in compare_list:
        ident_data_comp = compare_list['identical']

    if L1_err_compare != {}:
        for item in L1_err_compare:
            L1_err_compare[item]['expect'] = gamer_abs_path + '/' + compare_list['compare'][item]['expect']
            L1_err_compare[item]['result'] = gamer_abs_path + '/' + compare_list['compare'][item]['result']
    if ident_data_comp != {}:
        for item in ident_data_comp:
            ident_data_comp[item]['expect'] = gamer_abs_path + '/' + compare_list['identical'][item]['expect']
            ident_data_comp[item]['result'] = gamer_abs_path + '/' + compare_list['identical'][item]['result']

    return L1_err_compare, ident_data_comp


def compare_identical( result_file, expect_file, data_type='HDF5', **kwargs ):
    """
    Parameters
    ----------

    result_file : string
       Directory of the test data.
    expect_file : string
       Directory of the reference data.
    level       : string ( level[0/1/2] )
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
    check_dict_key( ['logger', 'error_allowed'], kwargs, "kwargs" )

    error_allowed = kwargs['error_allowed']
    logger        = kwargs['logger']
    # TODO: related to the step 2 in this function
    out_log       = LogPipe( logger, logging.DEBUG )

    fail_or_not  = False
    compare_fail = False

    if data_type == 'HDF5':
        #1. Load result informations and expect informations
        compare_program = gamer_abs_path + '/tool/analysis/gamer_compare_data/GAMER_CompareData'
        compare_result  = gamer_abs_path + '/regression_test/compare_result'

        result_info = hdf_info_read(result_file)
        expect_info = hdf_info_read(expect_file)

        #2. Run data compare program
        cmd = [compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',str(error_allowed),'-c','-m']
        try:
            with open('compare.log', 'w') as out_file:
                subprocess.check_call( cmd, stderr=out_log, stdout=out_file )
        except:
            subprocess.check_call( ['rm', 'compare.log'] )
            if not os.path.isfile(compare_result): comapre_fail = True
            fail_or_not = True

        #2.1 execution error of compare tool
        if compare_fail:
            logger.error( "The execution of '[%s]' is fail."%(" ".join(cmd)) )

        #3. Check if result equal to expect by reading compare_result
        with open( compare_result, 'r' ) as f:
            lines = f.readlines()
            for line in lines:
                if line[0] in ['#', '\n']:    continue      # comment and empty line
                fail_or_not = True
                break

        if fail_or_not:
            logger.debug('Result data is not identical to expect data')
            logger.debug('Error is greater than expect.')
            #logger.debug('Error is greater than expect. Expected: %.4e. Test: %.4e.'%(float(error_allowed), err))
            str_len = str(max( len(expect_file), len(result_file), 50 ))
            str_format = "%-"+str_len+"s %-"+str_len+"s"
            logger.debug( 'Type      : '+str_format%("Expect",              "Result"             ) )
            logger.debug( 'File name : '+str_format%(expect_file,           result_file          ) )
            logger.debug( 'Git Branch: '+str_format%(expect_info.gitBranch, result_info.gitBranch) )
            logger.debug( 'Git Commit: '+str_format%(expect_info.gitCommit, result_info.gitCommit) )
            logger.debug( 'Unique ID : '+str_format%(expect_info.DataID,    result_info.DataID   ) )

    elif data_type == 'TEXT':
        #1. Load result and expect files
        a = np.loadtxt( result_file )
        b = np.loadtxt( expect_file )

        if a.shape != b.shape:
            fail_or_not = True
            logger.error('Data compare : data shapes are different.')
            out_log.close()
            return fail_or_not

        #err = np.abs(1 - a/b) # there is an issue of devided by zero
        err = np.max(np.abs(a - b))
        if err > float(error_allowed): fail_or_not = True

        if fail_or_not:
            logger.debug('Error is greater than expect. Expected: %.4e. Test: %.4e.'%(float(error_allowed), err))

    else:
        fail_or_not = True
        logger.error('Not supported data type: %s.'%(data_type))

    out_log.close()

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
    check_dict_key( ['logger', 'error_allowed'], kwargs, "kwargs" )

    logger        = kwargs['logger']
    error_allowed = kwargs['error_allowed']

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
            if a[key][j] > b[key][j] + error_allowed:
                greater = True
                logger.debug("%-5d: %+16e %+16e => Unaccepted error!"%(a["NGrid"][j], a[key][j], b[key][j]))
            else:
                logger.debug("%-5d: %+16e %+16e"%(a["NGrid"][j], a[key][j], b[key][j]))

    if greater:
        fail_or_not = True
        logger.debug('Test Error is greater than expected.')

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
    config, input_settings = read_yaml(config_path, 'config')
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
