import logging
import os
import re
import subprocess
import pandas as pd
import shutil as st

from log_pipe import LogPipe
from os.path import isdir

config_path = 'configs/Riemann/make_config'
gamer_abs_path = '/work1/xuanshan/gamer'
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

def analyze():
	return 0

def check_answer(actual, expect, mode='identicle',**kwargs):
	a = pd.DataFrame(actual)
	b = pd.DataFrame(expect)
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
		kwargs('logger').debug('data shapes are different.')


#seirpt self test
if __name__ == '__main__':
	config, input_settings = get_config(config_path)
	print(input_settings)
	os.chdir('/work1/xuanshan/gamer/bin/Riemann')
	for sets in input_settings:
		set_input(input_settings[sets])
	make(config)
#	copy_example(input_folder)
#	run()
#	print check_answer([1],[1])
	print('end')
