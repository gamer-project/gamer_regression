import logging
import os
import subprocess
import pandas as pd
import shutil as st

config_path = 'make_config'
gamer_abs_path = '/work1/xuanshan/gamer_test'
input_folder = gamer_abs_path + '/example/test_problem/Hydro/Riemann'

test_config = {'Enable':['MODEL=HYDRO','SERIAL'],\
	       'Disable':['GRAVITY','PARTICLE','SUPPORT_GRACKLE','GPU','LOAD_BALANCE=HILBERT','OPENMP']}

def get_config(config_path):
	config_file= open(config_path)
	config_text = config_file.readlines()

	config = {'Enable':[],'Disable':[]}
	for line in config_text:
		settings = line.rstrip().split('\t')
		if settings[0] == 'Enable':
			config['Enable'] = settings[1].split(',')
		elif settings[0] == 'Disable':
			config['Disable'] = settings[1].split(',')
	return config

#Edit gamer configuration settings
def make(config):
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
	os.chdir(gamer_abs_pathi + '/src')
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

def run(file_folder):
	#cupy input files to work directory
	run_directory = gamer_abs_path + '/bin'
	test_name = file_folder.split('/')[-1]
	try:
		os.chdir(run_directory)
		st.copytree(file_folder,test_name)
		os.chdir(test_name)
		st.copy('../gamer','.')
	except:
		print 'Error on create work directory.'
	#run gamer
	try:
		subprocess.check_call(['./gamer'])
	except subprocess.CalledProcessErro , err:
		print 'err', err.cmd

	return 0

def analyze():

	return 0

#seirpt self test
if __name__ == '__main__':
#	config = get_config(config_path)
#	make(config)
	run(input_folder)
