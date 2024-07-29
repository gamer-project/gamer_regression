from __future__ import print_function
import logging
import os
from os.path import isdir,isfile
import sys
import subprocess
import numpy as np
import copy
import re

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

import script.girder_inscript as gi
from script.hdf5_file_config import hdf_info_read
from script.log_pipe import LogPipe
from script.utilities import *


####################################################################################################
# Classes
####################################################################################################
class gamer_test():
    def __init__( self, name, config, gamer_abs_path, ch, file_handler, err_level ):
        self.name           = name
        self.config         = config
        self.err_level      = err_level
        self.gamer_abs_path = gamer_abs_path
        self.src_path       = gamer_abs_path + '/src'
        self.bin_path       = gamer_abs_path + '/bin/' + self.name
        self.ref_path       = gamer_abs_path + '/regression_test/tests/' + config["name"]
        self.tool_path      = gamer_abs_path + '/tool/analysis/gamer_compare_data'
        self.status         = STATUS.SUCCESS
        self.reason         = ""
        self.logger         = set_up_logger( name, ch, file_handler )
        self.gh             = None
        self.gh_logger      = set_up_logger( 'girder', ch, file_handler )
        self.gh_has_list    = False
        self.yh_folder_dict = {}
        return

    def run_all_cases( self, **kwargs ):
        # 1. make the directory for the test
        if isdir( self.bin_path ):
            self.logger.warning('Test folder (%s) exist. ALL the original data and your scripts will be removed!'%(self.bin_path))
            subprocess.check_call(['rm', '-rf', self.bin_path])

        os.mkdir( self.bin_path )

        for i, case in enumerate(self.config['cases']):
            self.logger.info('Start running case: %d'%i)

            os.chdir(self.src_path)
            if self.compile_gamer( i, **kwargs )               != STATUS.SUCCESS: return self.status
            if self.copy_case( i, **kwargs )                   != STATUS.SUCCESS: return self.status
            os.chdir(self.bin_path+'/case_%02d'%i)
            if self.set_input( i, **kwargs )                   != STATUS.SUCCESS: return self.status
            if self.execute_scripts( 'pre_script', **kwargs )  != STATUS.SUCCESS: return self.status
            if self.run_gamer( i, **kwargs )                   != STATUS.SUCCESS: return self.status
            if self.execute_scripts( 'post_script', **kwargs ) != STATUS.SUCCESS: return self.status

            self.logger.info('End of running case: %d'%i)

        return self.status

    def compile_gamer( self, case_num, **kwargs ):
        self.logger.info('Start compiling GAMER')
        out_log = LogPipe( self.logger, logging.DEBUG )

        # 1. Back up the original Makefile
        keep_makefile = isfile('Makefile')
        if keep_makefile: subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

        # 2. Get commands to modify Makefile.
        cmd = generate_modify_command( self.config['cases'][case_num]['Makefile'], **kwargs )

        try:
            self.logger.debug("Generating Makefile using: %s"%(" ".join(cmd)))
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError:
            self.set_fail_test("Error while editing Makefile.", STATUS.EDITING_FAIL)
            if keep_makefile:
                subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
                subprocess.check_call(['rm', 'Makefile.origin'])
            out_log.close()
            return self.status

        # 3. Compile GAMER
        try:
            subprocess.check_call( ['make', 'clean'], stderr=out_log )
            subprocess.check_call( ['make -j > make.log'], stderr=out_log, shell=True )
            subprocess.check_call( ['rm', 'make.log'] )
        except subprocess.CalledProcessError:
            self.set_fail_test("Compiling error.", STATUS.COMPILE_ERR)
            return self.status

        finally:
            # Repair Makefile
            if keep_makefile:
                subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
                subprocess.check_call(['rm', 'Makefile.origin'])
            else:
                subprocess.check_call(['rm', 'Makefile'])

            out_log.close()

        # 4. Check if gamer exist
        if self.file_not_exist('./gamer'): return self.status

        self.logger.info('Compiling GAMER done.')

        return self.status

    def copy_case( self, case_num, **kwargs ):
        """
        Copy input files and GAMER to work directory.
        """
        case_dir   = self.bin_path + '/case_%02d'%case_num
        origin_dir = self.ref_path + '/Inputs'

        self.logger.info('Copying the test folder: %s ---> %s'%(origin_dir, case_dir))
        try:
            subprocess.check_call(['cp', '-r', origin_dir, case_dir])
            subprocess.check_call(['cp', self.src_path+'/gamer', case_dir])
            subprocess.check_call(['cp', self.src_path+'/Makefile.log', case_dir])
        except:
            self.set_fail_test('Error when copying to %s.'%case_dir, STATUS.COPY_FILES)
        self.logger.info('Copy completed.')

        return self.status

    def set_input( self, case_num, **kwargs ):
        for input_file, settings in self.config['cases'][case_num].items():
            cmds = []
            if input_file == "Makefile": continue

            for key, val in settings.items():
                cmds.append(['sed', '-i', 's/%-29s/%-29s%-4s #/g'%(key,key,val), input_file])

            self.logger.info('Editing %s.'%input_file)
            try:
                for cmd in cmds:
                    subprocess.check_call(cmd)
            except:
                self.set_fail_test('Error on editing %s.'%input_file, STATUS.EDIT_FILE)
            self.logger.info('Editing completed.')

        return self.status

    def execute_scripts( self, mode, **kwargs ):
        self.logger.info('Start execute scripts. Mode: %s'%mode)
        if mode not in ['pre_script', 'post_script', 'user_compare_script']:
            self.set_fail_test("Wrong mode of executing scripts.", STATUS.FAIL)
            return self.status

        out_log = LogPipe(self.logger, logging.DEBUG)
        for script in self.config[mode]:
            if self.file_not_exist( script ): break
            try:
                self.logger.info('Executing: %s'%script)
                subprocess.check_call( ['sh', script, self.bin_path], stderr=out_log )
            except:
                self.set_fail_test("Error while executing %s."%script, STATUS.EXTERNAL)
                break
        out_log.close()
        self.logger.info('Done execute scripts.')
        return self.status

    def run_gamer( self, case_num, **kwargs ):
        out_log = LogPipe( self.logger, logging.DEBUG )
        run_mpi = False
        if "mpi" in self.config["cases"][case_num]["Makefile"]:
            run_mpi = self.config["cases"][case_num]["Makefile"]["mpi"]

        run_cmd  = "mpirun -map-by ppr:%d:socket:pe=%d --report-bindings "%(kwargs["mpi_rank"], kwargs["mpi_core_per_rank"]) if run_mpi else ""
        run_cmd += "./gamer 1>>log 2>&1"

        self.logger.info('Running GAMER.')
        try:
            subprocess.check_call( [run_cmd], stderr=out_log, shell=True )
            if not isfile('./Record__Note'):
                self.set_fail_test('No Record__Note in %s.'%self.name, STATUS.FAIL)
        except subprocess.CalledProcessError as err:
            self.set_fail_test('GAMER error', STATUS.EXTERNAL)
        finally:
            out_log.close()
        self.logger.info('GAMER done.')

        return self.status

    def get_reference_data( self, **kwargs ):
        # TODO: the path here is confusing
        for file_dict in self.config["reference"]:
            file_where, ref_path_to_file = file_dict["loc"].split(":")
            ref_path = ref_path_to_file.split('/')[:-1]
            ref_name = ref_path_to_file.split('/')[-1]

            temp = file_dict["name"].split('/')
            case = "" if len(temp) == 1 else temp[0]

            target_folder = self.bin_path + "/" + "reference" + "/" + case
            if not os.path.isdir(target_folder): os.makedirs(target_folder)

            if file_where == "local":
                self.logger.info( "Linking %s --> %s"%(ref_path_to_file, target_folder+'/'+ref_name) )
                try:
                    subprocess.check_call( ['ln', '-s', ref_path_to_file, target_folder+'/'+ref_name] )
                except:
                    self.set_fail_test( "Can not link file %s."%ref_path_to_file, STATUS.EXTERNAL )
            # TODO: change the name of cloud
            elif file_where == "cloud":
                # Init if girder is not used before
                if self.gh == None:
                    self.gh = gi.girder_handler( self.gamer_abs_path, self.gh_logger, self.yh_folder_dict )
                    self.yh_folder_dict = self.gh.home_folder_dict

                if not self.gh_has_list:
                    self.status = self.gh.download_compare_version_list()
                    if self.status != STATUS.SUCCESS:
                        self.set_fail_test( 'Download from girder fails', self.status )
                    else:
                        self.gh_has_list = True

                ver_latest = self.gh.get_latest_version( self.name )
                time       = ver_latest['time']
                ref_folder = self.name + "-" + str(time)

                file_id = self.gh.home_folder_dict[ref_folder]
                for path in ref_path:
                    file_id = file_id[path]
                file_id = file_id[ref_name]['_id']

                self.logger.info( "Downloading (name: %s/%s, id: %s) --> %s"%(ref_folder, ref_path_to_file, file_id, target_folder) )
                self.status = self.gh.download_file_by_id( file_id, target_folder )
                if self.status != STATUS.SUCCESS:
                    self.logger.error( "Download (name: %s/%s, id: %s) fails!"%(ref_folder, ref_path_to_file, file_id) )
            elif file_where == "url":
                self.set_fail_test( "Download from url is not supported yet.", STATUS.FAIL )
                return self.status
                # TODO: test download from url, the `-o` name should be wrong
                try:
                    subprocess.check_call( ["curl", ref_path_to_file, "-o", target_folder+'/'+ref_name] )
                except:
                    self.set_fail_test( "Download from %s fail!"%(ref_path_to_file), STATUS.DOWNLOAD )
            else:
                self.set_fail_test( "Unknown file location %s"%file_where, STATUS.DOWNLOAD )

            # exit if fail test
            if self.status != STATUS.SUCCESS: return self.status

        return self.status

    def get_machine_path( self, **kwargs ):
        """
        Get package paths from the config file
        """
        config_file = '%s/configs/%s.config'%(self.gamer_abs_path, kwargs['machine'])
        paths = {}

        # 1. Read necessary information from config file
        with open( config_file, 'r' ) as f:
            lines = f.readlines()

        for line in lines:
            if 'PATH' not in line: continue

            temp = list( filter( None, re.split(" |:=|\n", line) ) )
            try:
                paths[temp[0]] = temp[1]
            except:
                paths[temp[0]] = ''
        return paths

    def make_compare_tool( self, **kwargs ):
        """
        Make compare data program.
        """
        self.logger.info('Start compiling compare tool.')
        os.chdir( self.tool_path )
        out_log = LogPipe( self.logger, logging.DEBUG )

        cmds = []
        # 1. Back up makefile
        os.rename( 'Makefile', 'Makefile.origin' )
        with open('Makefile.origin') as f:
            makefile_content = f.read()

        # 2. Check settings in configs
        paths = self.get_machine_path( **kwargs )
        for package_name, package_path in paths.items():
            makefile_content = makefile_content.replace(package_name + " :=" , package_name + " := " + package_path + "\n#")

        if len(self.config["cases"]) > 1: self.logger.warning("We will only follow the first case setup of the Makefile.")
        make_config = self.config["cases"][0]["Makefile"]
        if "model" in make_config:
            if make_config["model"] == "HYDRO":
                makefile_content = makefile_content.replace("SIMU_OPTION += -DMODEL=HYDRO", "SIMU_OPTION += -DMODEL=HYDRO")
            elif make_config["model"] == "ELBDM":
                makefile_content = makefile_content.replace("SIMU_OPTION += -DMODEL=HYDRO", "SIMU_OPTION += -DMODEL=ELBDM")
            else:
                self.set_fail_test( "Unknown model (%s) for compare tool."%make_config["model"], STATUS.FAIL )

        if "double" in make_config:
            if make_config["double"]:
                makefile_content = makefile_content.replace("#SIMU_OPTION += -DFLOAT8", "SIMU_OPTION += -DFLOAT8")

        if "debug" in make_config:
            if make_config["debug"]:
                makefile_content = makefile_content.replace("#SIMU_OPTION += -DGAMER_DEBUG", "SIMU_OPTION += -DGAMER_DEBUG")

        if "hdf5" in make_config:
            if make_config["hdf5"]:
                makefile_content = makefile_content.replace("#SIMU_OPTION += -DSUPPORT_HDF5", "SIMU_OPTION += -DSUPPORT_HDF5")

        # 3. Modify makefile
        self.logger.info('Modifying the Makefile of compare tool.')
        with open('Makefile','w') as f:
            f.write(makefile_content)
        self.logger.info('Modification complete.')

        # 4. Compile
        self.logger.info('Compiling the compare tool.')
        try:
            subprocess.check_call( ['make','clean'], stderr=out_log )
            subprocess.check_call( ['make > make.log'], stderr=out_log, shell=True )
            os.remove('make.log')
            self.logger.info('Compilation complete.')
        except:
            self.set_fail_test('Error while compiling the compare tool.', STATUS.COMPILE_ERR)
        finally:
            # Repair makefile
            os.remove('Makefile')
            os.rename('Makefile.origin','Makefile')

        out_log.close()

        return self.status

    def compare_data( self, **kwargs ):
        """
        Check the answer of test result.

        Parameters
        ----------

        kwargs    :
           error_level : string
              The error allowed level.
        """
        self.logger.info('Start comparing data.')

        #Get the list of files need to be compare
        for file_dict in self.config["reference"]:
            #TODO: check the file path
            temp = file_dict["name"].split('/')
            case = "" if len(temp) == 1 else temp[0]

            file_where, ref_path_to_file = file_dict["loc"].split(":")
            ref_name = ref_path_to_file.split('/')[-1]

            current_file   = self.bin_path + "/"           + file_dict["name"]
            reference_file = self.bin_path + "/reference/" + case + '/' + ref_name
            if self.file_not_exist( current_file   ): return self.status
            if self.file_not_exist( reference_file ): return self.status

            if file_dict["file_type"] == "TEXT":
                fail = compare_text( current_file, reference_file, self.config["levels"][self.err_level], logger=self.logger, **kwargs )
            elif file_dict["file_type"] == "HDF5":
                fail = compare_hdf5( current_file, reference_file, self.config["levels"][self.err_level], self.tool_path, logger=self.logger, **kwargs )
            elif file_dict["file_type"] == "NOTE":
                fail = compare_note( current_file, reference_file, logger=self.logger, **kwargs )
            else:
                print("compare unknow")

            if fail: self.set_fail_test( "Fail data comparison.", STATUS.COMPARISON )

        self.logger.info('Done comparing data.')
        return self.status

    def set_fail_test( self, reason, status_type ):
        self.status = status_type
        self.reason = reason
        self.logger.error( reason )
        return

    def file_not_exist( self, filename ):
        if isfile( filename ): return False
        reason = "%s does not exist."%filename
        self.set_fail_test( reason, STATUS.MISSING_FILE )
        return True



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
    cmd = [kwargs["py_exe"], "configure.py"]
    # 0. machine configuration
    cmd.append("--machine="+kwargs["machine"])

    # 1. simulation and miscellaneous options
    for key, val in config.items():
        cmd.append("--%s=%s"%(key, val))

    # 2. user force enable options
    # cmd.append("--hdf5=True")  # Enable HDF5 in all test
    #for arg in kwargs["force_args"]:
    #    cmd.append(arg)

    return cmd


# TODO: support the user compare range(data)
def compare_text( result_file, expect_file, err_allowed, **kwargs ):
    check_dict_key( ['logger'], kwargs, "kwargs" )
    logger       = kwargs['logger']
    fail_compare = False

    logger.info("Comparing TEXT: %s <--> %s"%(result_file, expect_file))

    a = np.loadtxt( result_file )
    b = np.loadtxt( expect_file )

    if a.shape != b.shape:
        fail_compare = True
        logger.error('Data compare : data shapes are different.')
        return fail_compare

    #err = np.abs(1 - a/b) # there is an issue of devided by zero
    err = np.max(np.abs(a - b))

    if err > err_allowed:
        fail_compare = True
        logger.debug('Error is greater than expect. Expected: %.4e. Test: %.4e.'%(err_allowed, err))

    logger.info("Comparing TEXT done.")

    return fail_compare


def compare_hdf5( result_file, expect_file, err_allowed, tool_path, **kwargs ):
    check_dict_key( ['logger'], kwargs, "kwargs" )
    logger       = kwargs['logger']
    out_log      = LogPipe( logger, logging.DEBUG )
    fail_compare = False

    logger.info("Comparing HDF5: %s <--> %s"%(result_file, expect_file))

    # 1. Load result informations and expect informations
    compare_program = tool_path + '/GAMER_CompareData'
    #TODO: fix the result path
    compare_result  = tool_path + '/compare_result'

    result_info = hdf_info_read( result_file )
    expect_info = hdf_info_read( expect_file )

    # 2. Run data compare program
    cmd = [compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',str(err_allowed),'-c','-m']
    try:
        with open('compare.log', 'w') as out_file:
            subprocess.check_call( cmd, stderr=out_log, stdout=out_file )
    except:
        subprocess.check_call( ['rm', 'compare.log'] )
        if not os.path.isfile(compare_result): fail_compare = True
        logger.error( "The execution of '[%s]' fails."%(" ".join(cmd)) )
        out_log.close()
        return fail_compare

    # 2. Check if result equal to expect by reading compare_result
    with open( compare_result, 'r' ) as f:
        lines = f.readlines()
        for line in lines:
            if line[0] in ['#', '\n']:    continue      # comment and empty line
            fail_compare = True
            break

    if fail_compare:
        logger.error('Result data is not identical to expect data')
        logger.error('Error is greater than expected.')
        str_len = str(max( len(expect_file), len(result_file), 50 ))
        str_format = "%-"+str_len+"s %-"+str_len+"s"
        logger.error( 'Type      : '+str_format%("Expect",              "Result"             ) )
        logger.error( 'File name : '+str_format%(expect_file,           result_file          ) )
        logger.error( 'Git Branch: '+str_format%(expect_info.gitBranch, result_info.gitBranch) )
        logger.error( 'Git Commit: '+str_format%(expect_info.gitCommit, result_info.gitCommit) )
        logger.error( 'Unique ID : '+str_format%(expect_info.DataID,    result_info.DataID   ) )

    logger.info("Comparing HDF5 done.")

    out_log.close()

    return fail_compare


def compare_note( result_note, expect_note, **kwargs ):
    """
    Compare the Record__Note files
    """
    logger       = kwargs['logger']
    fail_compare = False

    #TODO: return fail if comparing Record_Note is necessary
    if not isfile( result_note ):
        logger.error( "Result Record__Note (%s) does not exist!"%result_note )
        #fail_compare = True
        return fail_compare

    if not isfile( expect_note ):
        logger.error( "Expect Record__Note (%s) does not exist!"%expect_note )
        #fail_compare = True
        return fail_compare

    logger.info( "Comparing Record__Note: %s <-> %s"%(result_note, expect_note) )

    para_result = store_note_para( result_note )
    para_expect = store_note_para( expect_note )
    diff_para   = compare_para( para_result, para_expect )

    logger.debug("%-30s | %40s | %40s |"%("Parameter name", "result parameter", "expect parameter"))
    for key in diff_para["1"]:
        logger.debug("%-30s | %40s | %40s |"%(key, diff_para["1"][key], diff_para["2"][key]))
    logger.info("Comparison of Record__Note done.")

    return fail_compare


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

    gamer_abs_path = '/work1/xuanshan/gamer'
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
