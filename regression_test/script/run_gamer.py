import logging
import os
import re
import subprocess
import pandas as pd
import shutil as st
import numpy as np

from log_pipe import LogPipe
from os.path import isdir,isfile,walk

gamer_abs_path = '/work1/xuanshan/gamer'
config_path = gamer_abs_path + '/regression_test/test/Riemann/configs'
analyze_path = gamer_abs_path + '/regression_test/tests'
input_folder = gamer_abs_path + '/example/test_problem/Hydro/Riemann'

def get_config(config_path):
	config_file= open(config_path)
	config_text = config_file.readlines()
	#Grep settings in config file
	config	= {'Enable':[],'Disable':[]}
	setting	= []
	error	= {}
	for line in config_text:
		if 'MAKE_CONFIG:' in line:
			mode = 'MAKE'
			continue
		elif 'INPUT_SETTINGS:' in line:
			mode = 'INPUT'
			continue

		if mode == 'MAKE':
			settings = line.rstrip().split('\t')
			if settings[0] == 'Enable':
				config['Enable'] = settings[1].split(',')
			elif settings[0] == 'Disable':
				config['Disable'] = settings[1].split(',')
		elif mode == 'INPUT':
			settings = line
			setting.append(settings)
			
	#Grep settings for input setting
	input_settings = {}
	for s in setting:
		if 'input' in s:
			set_name=s.replace(':\n','')
			input_settings[set_name] = {}
			continue
		if 'Input__Parameter' in s:
			Input_file = 'Input__Parameter'
			input_settings[set_name][Input_file] = []
			continue
		elif 'Input__Flag_Lohner' in s:
			Input_file = 'Input__Flag_Lohner'
			input_settings[set_name][Input_file] = []
			continue
		elif 'Input_TestProb' in s:
			Input_file = 'Input_TestProb'
			input_settings[set_name][Input_file] = []
			continue
		ss = re.split('\s*',s)
		input_settings[set_name][Input_file].append(ss)

	return config, input_settings
 
#Edit gamer configuration settings
def make(config,**kwargs):
#	get commands to midify Makefile.
	cmds = []
#	add enable options
	for enable_option in config['Enable']:
		cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_option,enable_option),'Makefile'])
		#if 'OPENMP' in enable_option:
			#cmds.append(['sed','-i','s/CXX         = g++/#CXX         = g++/g','Makefile'])
			#cmds.append(['sed','-i','s/#CXX         = $(MPI_PATH)/CXX         = $(MPI_PATH)/g','Makefile'])
#	add disable options
	for disable_option in config['Disable']:
		cmds.append(['sed','-i','s/SIMU_OPTION += -D%s/#SIMU_OPTION += -D%s/g'%(disable_option,disable_option),'Makefile'])
#	Back up and modify Makefile
	current_path = os.getcwd()
	os.chdir(gamer_abs_path + '/src')
	subprocess.check_call(['cp', 'Makefile', 'Makefile.origin'])
#	Makefile configuration
	
	try:
		for cmd in cmds:
			subprocess.check_call(cmd)
	except subprocess.CalledProcessError , err:
		print 'err', err.cmd
#	Make
	try:
		subprocess.check_call(['make','clean'])
		subprocess.check_call(['make','-j'])
	except subprocess.CalledProcessError , err:
		kwargs['logger'].error('Compile error')
		print 'err', err.cmd
#	Repair Makefile
		subprocess.check_call(['cp', 'Makefile.origin', 'Makefile'])
		subprocess.check_call(['rm', 'Makefile.origin'])
		return 1
#	Repair Makefile
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
		cmds.append(['sed','-i','s/OPT__OUTPUT_TOTAL/OPT__OUTPUT_TOTAL%14i \#/g'%(2),input_file])
		for i in input_settings[input_file]:
			cmds.append(['sed','-i','s/%-29s/%-29s%-4s \#/g'%(i[0],i[0],i[1]),input_file])
	
	for cmd in cmds:
		subprocess.check_call(cmd)

def run(**kwargs):
#run gamer
	if len(kwargs) != 0:
		try:
			subprocess.check_call(['./gamer'])
		except subprocess.CalledProcessError, err:		
			kwargs['logger'].error('run_error in %s'%(kwargs['input_name']))
			return 1
	else:
		try:
			subprocess.check_call(['./gamer'])
		except:
			pass
	#out_log.close()
	#err_log.close()
	return 0

def analyze(test_name):
	analyze_file = gamer_abs_path + '/regression_test/test/' + test_name + '/run_analyze.sh'
	if isfile(analyze_file):
		try:
			subprocess.check_call(['sh',analyze_file])
		except subprocess.CalledProcessError, err:
			pass

def data_equal(result_file, expect_file, level='level0', data_type='binary',**kwargs):
	error_allowed = kwargs['error_allowed']
	print error_allowed
	if data_type == 'binary':
		compare_program = gamer_abs_path + '/tool/analysis/gamer_compare_data/GAMER_CompareData'
		compare_result = gamer_abs_path + '/regression_test/compare_result'

		subprocess.check_call([compare_program,'-i',result_file,'-j',expect_file,'-o',compare_result,'-e',error_allowed])
		compare_file = open(compare_result)
		lines = compare_file.readlines()
		
		if len(lines) > 1:
			kwargs['logger'].warning('Test Error is greater than expect.')
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
					kwargs['logger'].warning('Test Error is greater than expect.')
				else:
					return True
		else:
			print 'Data frame shapes are different.'
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
			kwargs['logger'].warning('Test Error is greater than expect.')
	else:
		print 'Data frame shapes are different.'
		kwargs['logger'].debug('Data compare : data shapes are different.')

def read_compare_list(test_name):
	compare_list_file = analyze_path + '/' + test_name + '/' + 'compare_results'
	list_file	  = open(compare_list_file)
	lines		  = list_file.readlines()
	L1_err_compare	  = {}
	ident_data_comp	  = {}

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
	return L1_err_compare, ident_data_comp

def check_answer(test_name,**kwargs):
	#check the answer of test result
	log = kwargs['logger']
	level = kwargs['error_level']

	#Get the list of files need to be compare
	err_comp_f, ident_comp_f = read_compare_list(test_name)

	#Start compare data files
	for err_file in err_comp_f:
		error_comp(err_comp_f[err_file]['result'],err_comp_f[err_file]['expect'],logger=log)
	for ident_file in ident_comp_f:
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
	print(input_settings)
	os.chdir('/work1/xuanshan/gamer/bin/Riemann')
	for sets in input_settings:
		set_input(input_settings[sets])
#	make(config)
#	copy_example(input_folder)
#	run()
#	print check_answer([1],[1])
#	analyze('AcousticWave')
#	check_answer('AcousticWave',logger=test_logger)
	print('end')
