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
config_path = gamer_abs_path + '/regression_test/configs/Riemann/make_config'
analyze_path = gamer_abs_path + '/regression_test/analysis'
input_folder = gamer_abs_path + '/example/test_problem/Hydro/Riemann'

test_config = {'Enable':['MODEL=HYDRO','SERIAL'],\
	       'Disable':['GRAVITY','PARTICLE','SUPPORT_GRACKLE','GPU','LOAD_BALANCE=HILBERT','OPENMP']}

def get_config(config_path):
	config_file= open(config_path)
	config_text = config_file.readlines()
	#Grep settings in config file
	config = {'Enable':[],'Disable':[]}
	setting = []
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
			input_settings[set_name]=[]
			continue
		ss = re.split('\s*',s)
		input_settings[set_name].append(ss)

	return config, input_settings
 
#Edit gamer configuration settings
def make(config,**kwargs):
#	get commands to midify Makefile.
	cmds = []
#	add enable options
	for enable_option in config['Enable']:
		cmds.append(['sed','-i','s/#SIMU_OPTION += -D%s/SIMU_OPTION += -D%s/g'%(enable_option,enable_option),'Makefile'])
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
		print 'err', err.cmd
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
	for i in input_settings:
		
		cmds.append(['sed','-i','s/%-29s/%-29s%-4s \#/g'%(i[0],i[0],i[1]),'Input__Parameter'])
	
	for cmd in cmds:
		subprocess.check_call(cmd)

def run(**kwargs):
#run gamer
	if len(kwargs) != 0:
		try:
			subprocess.check_call(['./gamer'])
		except subprocess.CalledProcessError, err:
			kwargs['logger'].error('run_error')
	else:
		try:
			subprocess.check_call(['./gamer'])
		except:
			pass
	#out_log.close()
	#err_log.close()

def analyze(test_name):
	analyze_file = gamer_abs_path + '/regression_test/analysis/' + test_name + '/run_analyze.sh'
	if isfile(analyze_file):
		try:
			subprocess.check_call(['sh',analyze_file])
		except subprocess.CalledProcessError, err:
			pass

def data_equal(result_file, expect_file, mode='identicle',**kwargs):
	a = pd.read_csv(result_file,header=0)
	b = pd.read_csv(expect_file,header=0)
	if a.shape == b.shape:
		if mode == 'identicle':
			return a.equals(b)
		elif mode == 'almost':
			err = a - b
			if err > 6e-10:
				return False
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

def check_answer(test_name,**kwargs):
	#check the answer of test result
	log = kwargs['logger']
	c_file_list = analyze_path + '/' + test_name + '/compare_results'
	cfl           = open(c_file_list)
	lines         = cfl.readlines()
	err_comp_f    = {}
	ident_comp_f  = {}
	almost_ident_f= {}
	for line in lines:
		if 'Error compare' in line:
			mode = 'error compare'
			continue
		if 'Data identicle' in line:
			mode = 'identicle'
			continue
		l = re.split('\s*',line)
		if mode == 'error compare':
			if 'compare file' in line:
				err_comp_f[l[2]] = {}
				comp_f = l[2]
				continue
			elif 'expect' in line:
				err_comp_f[comp_f]['expect'] = analyze_path + '/' + l[1]
				continue
			elif 'result' in line:
				err_comp_f[comp_f]['result'] = analyze_path + '/' + l[1]
				continue
		if mode == 'identicle':
			if 'compare file' in line:
				err_comp_f[l[2]] = {}
				comp_f = l[2]
				continue
			elif 'expect' in line:
				err_comp_f[comp_f]['expect'] = analyze_path + '/' + l[1]
				continue
			elif 'result' in line:
				err_comp_f[comp_f]['result'] = analyze_path + '/' + l[1]
				continue

	for err_file in err_comp_f:
		error_comp(err_comp_f[err_file]['result'],err_comp_f[err_file]['expect'],logger=log)
	for ident_file in ident_comp_f:
		data_equal(ident_comp_f[ident_file]['result'],ident_comp_f[ident_file]['expect'],logger=log)

#seirpt self test
if __name__ == '__main__':
	test_logger = logging.getLogger('test')
	logging.basicConfig(level=0)
	ch = logging.StreamHandler()
	std_formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
	ch.setLevel(logging.DEBUG)
	ch.setFormatter(std_formatter)
	test_logger.setLevel(logging.DEBUG)
	test_logger.propagate = False
	test_logger.addHandler(ch)

#	config, input_settings = get_config(config_path)
#	print(input_settings)
#	os.chdir('/work1/xuanshan/gamer/bin/Riemann')
#	for sets in input_settings:
#		set_input(input_settings[sets])
#	make(config)
#	copy_example(input_folder)
#	run()
#	print check_answer([1],[1])
#	analyze('AcousticWave')
	check_answer('AcousticWave',logger=test_logger)
	print('end')
