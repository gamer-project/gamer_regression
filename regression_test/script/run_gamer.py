from __future__ import print_function
import logging
import os
import re
import yaml
import subprocess
import pandas as pd
import shutil as st
import numpy as np

from hdf5_file_config import hdf_info_read
from log_pipe import LogPipe
from os.path import isdir,isfile

gamer_abs_path = '/work1/xuanshan/gamer'
config_path = gamer_abs_path + '/regression_test/tests/AGORA_IsolatedGalaxy/configs'
analyze_path = gamer_abs_path + '/regression_test/tests'
input_folder = gamer_abs_path + '/example/test_problem/Hydro/'

def get_config(config_path):
	with open(config_path) as stream:
		data = yaml.load(stream)


	return data['MAKE_CONFIG'], data['INPUT_SETTINGS']

def read_test_group():
	with open('group') as stream:
		data = yaml.load(stream)
	return data
 
def generate_modify_command(config):
#Edit gamer configuration settings
	cmds = []
	#Generate enable and disable config command
	#Enable
	for enable_option in config['Enable']:
		cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_option,enable_option),'Makefile'])
	#Disable
	for disable_option in config['Disable']:
		cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_option,disable_option),'Makefile'])

	#Generate variable midify command
	if 'Variable' in config:
		for var in config['Variable']:
			cmds.append(['sed','-i','s/%s/%s\t \#/g'%(var,var,config['Variable'][var])])
	return cmds

def make(config,**kwargs):
	out_log = LogPipe(kwargs['logger'],logging.DEBUG)

#	Back up and modify Makefile
	subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])

#	Makefile configuration
#	get commands to midify Makefile.
	cmds = generate_modify_command(config)
	
	try:
		for cmd in cmds:
			subprocess.check_call(cmd)
	except subprocess.CalledProcessError:
		print('Error in editing Makefile')
	mf = open('Makefile')
#	Make
	try:
		subprocess.check_call(['make','clean'],stderr=out_log)
		subprocess.check_call(['make','-j'],stderr=out_log)
	except subprocess.CalledProcessError:
		kwargs['logger'].error('compiling error')
		print('Error in compile')
		return 1
	finally:
		out_log.close()
#	Repair Makefile
		subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
		subprocess.check_call(['rm', 'Makefile.origin'])
		#check if compile successful
		if not isfile('./gamer'):
			kwargs['logger'].error('compiling error')
			print('Error in compile')
			return 1

	return 0

def make_compare_tool(test_path,make_config):
#	Make compare data program
	cmds = []
#	Back up makefile
	subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])
#	Chekc if setting in hydro
	if 'Hydro' in test_path:
		cmds.append(['sed','-i','s/DMODEL=ELBDM/DMODEL=HYDRO/g','Makefile'])
	elif 'ELBDM' in test_path:
		cmds.append(['sed','-i','s/DMODEL=HYDRO/DMODEL=ELBDM/g','Makefile'])
#	Check settings in configs
	for enable_config in make_config['Enable']:
		cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_config,enable_config),'Makefile'])
			
	for disable_config in make_config['Disable']:
		cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_config,disable_config),'Makefile'])
		
	try:
		for cmd in cmds:
			subprocess.check_call(cmd)
	except:
		pass

	try:
		subprocess.check_call(['make','clean'])
		subprocess.check_call(['make'])
	except:
		pass
		
	subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
	subprocess.check_call(['rm', 'Makefile.origin'])
	return 0

def copy_example(file_folder,test_folder):
	#cupy input files to work directory
	run_directory = gamer_abs_path + '/bin'
	try:
		if isdir(run_directory+'/'+test_folder):
			print('Test folder exist.')
		else:
			os.chdir(run_directory)
			st.copytree(file_folder,test_folder)
		os.chdir(run_directory+'/'+test_folder)
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
	#run gamer
	if len(kwargs) != 0:
		try:
			subprocess.check_call(['./gamer'],stderr=out_log)
		except subprocess.CalledProcessError as err:		
			kwargs['logger'].error('running error in %s'%(kwargs['input_name']))
			out_log.close()
			return 1
		#finally:
	else:
		try:
			subprocess.check_call(['./gamer'])
		except:
			out_log.close()
			return 1
	#err_log.close()
	out_log.close()
	return 0

def analyze(test_name,fails):
	analyze_file = gamer_abs_path + '/regression_test/test/' + test_name + '/run_analyze.sh'
	if isfile(analyze_file):
		try:
			subprocess.check_call(['sh',analyze_file])
		except subprocess.CalledProcessError:
			pass

def data_equal(result_file, expect_file, level='level0', data_type='HDF5',**kwargs):
	error_allowed = kwargs['error_allowed']
	
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
		

		subprocess.check_call([compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',error_allowed])
		compare_file = open(compare_result)
		lines = compare_file.readlines()
		
		if len(lines) > 14:
			kwargs['logger'].warning('Data_compare')
			kwargs['logger'].debug('Error is greater than expect')
			kwargs['logger'].debug('Exgect result info:')
			kwargs['logger'].debug('File name : %s' %expect_file)
			kwargs['logger'].debug('Git Branch: %s' %expect_info.gitBranch)
			kwargs['logger'].debug('Git Commit: %s' %expect_info.gitCommit)
			kwargs['logger'].debug('Unique ID : %s' %expect_info.DataID)
			kwargs['logger'].debug('Test result info:')
			kwargs['logger'].debug('File name : %s' %expect_file)
			kwargs['logger'].debug('Git Branch: %s' %result_info.gitBranch)
			kwargs['logger'].debug('Git Commit: %s' %result_info.gitCommit)
			kwargs['logger'].debug('Unique ID : %s' %result_info.DataID)
		else:
			return True

	elif data_type == 'text':
		a = pd.read_csv(result_file,header=0)
		b = pd.read_csv(expect_file,header=0)
		if a.shape == b.shape:
			if   level == 0:
				return a.equals(b)
			elif level == 1:
				err = a - b
				if err > 6e-10:
					kwargs['logger'].warning('Data_compare')
					kwargs['logger'].debug('Error is greater than expect')
				else:
					return True
		else:
			print('Data frame shapes are different.')
			kwargs['logger'].debug('Data compare : data shapes are different.')

def error_comp(result_file, expect_file,**kwargs):
	a = pd.read_csv(result_file,delimiter=r'\s+',dtype={'Error':np.float64})
	b = pd.read_csv(expect_file,delimiter=r'\s+',dtype={'Error':np.float64})

	greater = False
	if a.shape == b.shape:
		comp = a > b
		for row in comp:
			for element in comp[row]:
				if element:
					greater = True
					break
			if greater:
				break
	
		if greater:
			kwargs['logger'].warning('Data_compare')
			kwargs['logger'].debug('Test Error is greater than expect.')
	else:
		print('Data frame shapes are different.')
		kwargs['logger'].debug('Data compare : data shapes are different.')

def read_compare_list(test_name,fails):
	L1_err_compare  = {}
	ident_data_comp = {}
	compare_list_file = analyze_path + '/' + test_name + '/' + 'compare_results'
	with open(compare_list_file) as stream:
		compare_list = yaml.load(stream)

	if compare_list == None:
		return L1_err_compare, ident_data_comp

	if 'compare' in compare_list:
		L1_err_compare = compare_list['compare']
	if 'identicle' in compare_list:
		ident_data_comp = compare_list['identicle']
	
	if not L1_err_compare == None:
		for item in L1_err_compare:
			L1_err_compare[item]['expect'] = gamer_abs_path + '/' + compare_list['compare'][item]['expect']
			L1_err_compare[item]['result'] = gamer_abs_path + '/' + compare_list['compare'][item]['result']
	if not ident_data_comp == None:
		for item in ident_data_comp:
			ident_data_comp[item]['expect'] = gamer_abs_path + '/' + compare_list['identicle'][item]['expect']
			ident_data_comp[item]['result'] = gamer_abs_path + '/' + compare_list['identicle'][item]['result']

	# Remove the compare results pair due to the fial case 	
	for f in fails:
		for case in L1_err_compare:
			if f in L1_err_compare[case]['result']:
				del L1_err_compare[case]
		for case in ident_data_comp:
			if f in ident_data_comp[case]['result']:
				del ident_data_comp[case]
	
	return L1_err_compare, ident_data_comp

def read_compare_list_old(test_name,fails):
	compare_list_file = analyze_path + '/' + test_name + '/' + 'compare_results'
	list_file	  = open(compare_list_file)
	lines		  = list_file.readlines()
	L1_err_compare	  = {}
	ident_data_comp	  = {}
	cfs = []
	ifs = []

	for line in lines:
		if len(line) == 1:
			continue
		if 'Error compare' in line:
			mode = 'compare'
			continue
		elif 'Data identicle' in line:
			mode = 'identicle'
			continue
		l = re.split('\s*',line)
		if mode == 'compare':
			if 'compare file' in line:
				comp_f = l[2]
				cfs.append(comp_f)
				L1_err_compare[comp_f] = {}
				continue
			if 'expect' in line:
				L1_err_compare[comp_f]['expect'] = gamer_abs_path + '/' + l[1]
				continue
			elif 'result' in line:
				L1_err_compare[comp_f]['result'] = gamer_abs_path + '/' + l[1]
				continue
		elif mode == 'identicle':
			if 'compare file' in line:
				comp_f = l[2]
				ifs.append(comp_f)
				ident_data_comp[comp_f] = {}
				continue
			if 'expect' in line:
				ident_data_comp[comp_f]['expect'] = gamer_abs_path + '/' + l[1]
				continue
			elif 'result' in line:
				ident_data_comp[comp_f]['result'] = gamer_abs_path + '/' + l[1]
				continue
			elif 'error_level0' in line:
				ident_data_comp[comp_f]['level0'] = l[1]
				continue
			elif 'error_level1' in line:
				ident_data_comp[comp_f]['level1'] = l[1]
				continue	
	# Remove the compare results pair due to the fial case 	
	for f in fails:
		for case in cfs:
			if f in L1_err_compare[case]['result']:
				del L1_err_compare[case]
		for case in ifs:
			if f in ident_data_comp[case]['result']:
				del ident_data_comp[case]
	
	return L1_err_compare, ident_data_comp

def check_answer(test_name,fails,**kwargs):
	#check the answer of test result
	log = kwargs['logger']
	if 'error_level' in kwargs:
		level = kwargs['error_level']

	#Get the list of files need to be compare
	err_comp_f, ident_comp_f = read_compare_list(test_name,fails)
	#Start compare data files
	
	if len(err_comp_f) > 0:
		for err_file in err_comp_f:
			if fails:
				break
			if not isfile(err_comp_f[err_file]['result']):
				kwargs['logger'].error('No such error result file in the path.')
				break
			elif not isfile(err_comp_f[err_file]['expect']):
				kwargs['logger'].error('No such error expect file in the path')
				break
			error_comp(err_comp_f[err_file]['result'],err_comp_f[err_file]['expect'],logger=log)
	if len(ident_comp_f) > 0:
		for ident_file in ident_comp_f:
			f = False
			for fail in fails:
				if fail in ident_comp_f[ident_file]['result']:
					f = True
					break
			if f:
				continue

			if not isfile(ident_comp_f[ident_file]['result']):
				kwargs['logger'].error('No such result file in the path.')
				break
			elif not isfile(ident_comp_f[ident_file]['expect']):
				kwargs['logger'].error('No such expect file in the path')
				break
			data_equal(ident_comp_f[ident_file]['result'],ident_comp_f[ident_file]['expect'],logger=log,error_allowed=ident_comp_f[ident_file][level])

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
	#	set_input(input_settings[sets])
#	make(config)
#	copy_example(input_folder)
#	run()
#	print check_answer([1],[1])
#	analyze('AcousticWave')
#	check_answer('AcousticWave',logger=test_logger)
	print('end')
