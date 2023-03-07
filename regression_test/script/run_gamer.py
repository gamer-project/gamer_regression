from __future__ import print_function
import logging
import os
import re
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
from os.path import isdir,isfile

gamer_abs_path = '/work1/xuanshan/gamer'
config_path = gamer_abs_path + '/regression_test/tests/AGORA_IsolatedGalaxy/configs'
analyze_path = gamer_abs_path + '/regression_test/tests'
input_folder = gamer_abs_path + '/example/test_problem/Hydro/'

def get_config(config_path):
    with open(config_path) as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)

    return data['MAKE_CONFIG'], data['INPUT_SETTINGS']

def read_test_group():
    with open('group') as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)
    return data
 
def generate_modify_command(config):
#Edit gamer configuration settings
    cmds = []
    #Generate enable and disable config command
    #Enable HDF5 in all test
    cmds.append(['sed','-i','s/#SIMU_OPTION += -DSUPPORT_HDF5/SIMU_OPTION += -DSUPPORT_HDF5/g','Makefile'])
    #Enable options
    for enable_option in config['Enable']:
        cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_option,enable_option),'Makefile'])
    #Disable options
    for disable_option in config['Disable']:
        cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_option,disable_option),'Makefile'])

    #Generate variable modify command
    if 'Variable' in config:
        for var in config['Variable']:
            cmds.append(['sed','-i','s/%s/%s\t \#/g'%(var,var,config['Variable'][var])])
    return cmds

def make(config,**kwargs):
    out_log = LogPipe(kwargs['logger'],logging.DEBUG)

#    Back up and modify Makefile
    subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

#    Makefile configuration
#    get commands to midify Makefile.
    cmds = generate_modify_command(config)
    
    try:
        for cmd in cmds:
            subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print('Error in editing Makefile')
    mf = open('Makefile')
#    Make
    try:
        subprocess.check_call(['make','clean'],stderr=out_log)
        subprocess.check_call(['make','-j'],stderr=out_log)
    except subprocess.CalledProcessError:
        kwargs['logger'].error('compiling error')
        print('Error in compile')
        return 1
    finally:
        out_log.close()
#    Repair Makefile
        subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
        subprocess.check_call(['rm', 'Makefile.origin'])
        #check if compile successful
        if not isfile('./gamer'):
            kwargs['logger'].error('compiling error')
            print('Error in compile')
            return 1

    return 0

def make_compare_tool(test_path,make_config):
#    Make compare data program
    cmds = []
#    Back up makefile
    subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])
#    Chekc if setting in hydro
    if 'Hydro' in test_path:
        cmds.append(['sed','-i','s/DMODEL=ELBDM/DMODEL=HYDRO/g','Makefile'])
    elif 'ELBDM' in test_path:
        cmds.append(['sed','-i','s/DMODEL=HYDRO/DMODEL=ELBDM/g','Makefile'])
    else:
        print("Not supported model in GAMER.")

#    Check settings in configs
    for enable_config in make_config['Enable']:
        cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_config,enable_config),'Makefile'])
            
    for disable_config in make_config['Disable']:
        cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_config,disable_config),'Makefile'])
        
    try:
        for cmd in cmds:
            subprocess.check_call(cmd)
    except:
        #TODO: should here be echo the fail cmd
        pass

    try:
        subprocess.check_call(['make','clean'])
        subprocess.check_call(['make'])
    except:
        #TODO: should here be echo the fail cmd
        pass
        
    subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
    subprocess.check_call(['rm', 'Makefile.origin'])
    return 0

def copy_example(file_folder,test_folder):
    #cupy input files to work directory
    run_directory = gamer_abs_path + '/bin'
    try:
        if isdir(run_directory+'/'+test_folder):
            print('Test folder exist. ALL the data will be removed and replaced by the new regression test. ')
        else:
            os.chdir(run_directory)
            st.copytree(file_folder,test_folder)
        os.chdir( run_directory+'/'+test_folder )
        subprocess.check_call(['sh', 'clean.sh'])
        st.copy('../gamer','.')
    except:
        print('Error on create work directory.')

def set_input(input_settings):
    cmds = []
    for input_file in input_settings:
        if input_settings[input_file] == None:
            continue
        #Set gamer dump file as hdf5 file
        cmds.append(['sed','-i','s/OPT__OUTPUT_TOTAL/OPT__OUTPUT_TOTAL%14i #/g'%(1),input_file])
        #Set other input parameter
        for item in input_settings[input_file]:
            cmds.append(['sed','-i','s/%-29s/%-29s%-4s #/g'%(item,item,input_settings[input_file][item]),input_file])
    for cmd in cmds:
        subprocess.check_call(cmd)

def run(**kwargs):
    out_log = LogPipe(kwargs['logger'],logging.DEBUG)

    run_cmd = './gamer'
    if len(kwargs) != 0:  # prepare for the mpirun
        run_cmd = './gamer'
    
    #run gamer
    run_status = 0
    try:
        subprocess.check_call([run_cmd],stderr=out_log)
        if not isfile('./Record__Note'):
            kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
            run_status = 1 

    except subprocess.CalledProcessError as err:        
        kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
        run_status = 1 

    finally:
        out_log.close()
    
    return run_status

def analyze(test_name,fails):
    analyze_file = gamer_abs_path + '/regression_test/test/' + test_name + '/run_analyze.sh'
    
    if not isfile(analyze_file):    return # No need to analyze this test
    
    try:
        subprocess.check_call(['sh',analyze_file])
    except subprocess.CalledProcessError:
        pass

def data_equal(result_file, expect_file, level='level0', data_type='HDF5',**kwargs):
    error_allowed = kwargs['error_allowed']
    fail_or_not = False

    #load result informations and expect informations
    if data_type == 'HDF5':
        compare_program = gamer_abs_path + '/tool/analysis/gamer_compare_data/GAMER_CompareData'
        compare_result = gamer_abs_path + '/regression_test/compare_result'
        
        result_info = hdf_info_read(result_file)
        expect_info = hdf_info_read(expect_file)

        kwargs['logger'].info('Expect result is run from the version below.')
        kwargs['logger'].info('File name : %s' %expect_file)
        kwargs['logger'].info('Git Branch: %s' %expect_info.gitBranch)
        kwargs['logger'].info('Git Commit: %s' %expect_info.gitCommit)
        kwargs['logger'].info('Unique ID : %s' %expect_info.DataID)
        
    #run data compare program
        subprocess.check_call([compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',error_allowed])
    #check if result equal to expect
        compare_file = open(compare_result)
        lines = compare_file.readlines()
        result_lines = []
        for line in lines:
            if line[0] == '#':    continue
            result_lines.append(line)
        
        #print(result_lines)  #@@@
        if len(result_lines) > 4:    fail_or_not = True

    elif data_type == 'text':
        a = pd.read_csv(result_file,header=0)
        b = pd.read_csv(expect_file,header=0)

        if a.shape != b.shape:
            fail_or_not = True
            print('Data frame shapes are different.')
            kwargs['logger'].debug('Data compare : data shapes are different.')
            return fail_or_not
            
        if   level == 'level0':
            fail_or_not = a.equals(b)
        elif level == 'level1':
            err = a - b
            if err > 6e-10:  # TODO: Replace to the wanted error
                fail_or_not = True
                kwargs['logger'].warning('Data_compare')
                kwargs['logger'].debug('Error is greater than expect')
        else:
            print("Error level (%s) is not supported"%(level))
    else:
        fail_or_not = True
        print("Not supported data type: %s."%(data_type))
        kwargs['logger'].debug('Not supported data type: %s.'%(data_type))

    return fail_or_not

def error_comp(result_file, expect_file,**kwargs):
    a = pd.read_csv(result_file,delimiter=r'\s+',dtype={'Error':np.float64})
    b = pd.read_csv(expect_file,delimiter=r'\s+',dtype={'Error':np.float64})

    fail_or_not = False
    greater = False

    if a.shape != b.shape: 
        fail_or_not = True
        print('Data frame shapes are different.')
        kwargs['logger'].debug('Data compare : data shapes are different.')
        return fail_or_not, result_file, expect_file
        
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
        kwargs['logger'].warning('Data_compare')
        kwargs['logger'].debug('Test Error is greater than expect.')

    return fail_or_not

def read_compare_list(test_name,fails):
    L1_err_compare  = {}
    ident_data_comp = {}
    compare_list_file = analyze_path + '/' + test_name + '/' + 'compare_results'
    with open(compare_list_file) as stream:
        compare_list = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)

    if compare_list == None:    return L1_err_compare, ident_data_comp

    if 'compare' in compare_list:
        L1_err_compare = compare_list['compare']
    if 'identicle' in compare_list:
        ident_data_comp = compare_list['identicle']
    
    if L1_err_compare != {}:
        for item in ident_data_comp:
            L1_err_compare[item]['expect'] = gamer_abs_path + '/' + compare_list['compare'][item]['expect']
            L1_err_compare[item]['result'] = gamer_abs_path + '/' + compare_list['compare'][item]['result']
    if ident_data_comp != {}:
        for item in ident_data_comp:
            ident_data_comp[item]['expect'] = gamer_abs_path + '/' + compare_list['identicle'][item]['expect']
            ident_data_comp[item]['result'] = gamer_abs_path + '/' + compare_list['identicle'][item]['result']

    # Remove the compare results pair due to the fail case     
    #for f in fails:
    #    for case in L1_err_compare:
    #        if f in L1_err_compare[case]['result']:
    #            del L1_err_compare[case]
    #    for case in ident_data_comp:
    #        if f in ident_data_comp[case]['result']:
    #            del ident_data_comp[case]
    
    return L1_err_compare, ident_data_comp


def check_answer(test_name,fails,**kwargs):
    #check the answer of test result
    log = kwargs['logger']
    if 'error_level' in kwargs:
        level = kwargs['error_level']

    #Get the list of files need to be compare
    err_comp_f, ident_comp_f = read_compare_list(test_name,fails)
    #Start compare data files
    compare_fails = []
    if len(err_comp_f) > 0:
        for err_file in err_comp_f:
            if fails:    break

            result_file = err_comp_f[err_file]['result']
            expect_file = err_comp_f[err_file]['expect']

            if not isfile( result_file ):
                kwargs['logger'].error('No such error result file in the path.')
                break
            if not isfile( expect_file ):
                kwargs['logger'].error('No such error expect file in the path')
                break

            fail_or_not = error_comp( result_file, expect_file, logger=log )
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
                kwargs['logger'].error('No such result file in the path.')
                break
            if not isfile( expect_file ):
                kwargs['logger'].error('No such expect file in the path.')
                break
            
            fail_or_not = data_equal( result_file, expect_file, logger=log, level=level, error_allowed=ident_comp_f[ident_file][level] )
            if fail_or_not:
                identical_fails.append([result_file,expect_file])

    #report the compare result in log 
    if len(identical_fails) > 0 or len(compare_fails) > 0:
        kwargs['logger'].warning('Data_compare')

    if len(identical_fails) > 0:
        kwargs['logger'].debug('Result data is not equal to expect data')
        for fail_files in identical_fails:
            result_info = hdf_info_read(fail_files[0])
            expect_info = hdf_info_read(fail_files[1])
            kwargs['logger'].debug('Expect result info:')
            kwargs['logger'].debug('File name : %s' %fail_files[1])
            kwargs['logger'].debug('Git Branch: %s' %expect_info.gitBranch)
            kwargs['logger'].debug('Git Commit: %s' %expect_info.gitCommit)
            kwargs['logger'].debug('Unique ID : %s' %expect_info.DataID)
            kwargs['logger'].debug('Test result info:')
            kwargs['logger'].debug('File name : %s' %fail_files[0])
            kwargs['logger'].debug('Git Branch: %s' %result_info.gitBranch)
            kwargs['logger'].debug('Git Commit: %s' %result_info.gitCommit)
            kwargs['logger'].debug('Unique ID : %s\n' %result_info.DataID)

    if len(compare_fails) > 0:
        kwargs['logger'].debug('Error compare result is greater than expect')


#seirpt self test
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
