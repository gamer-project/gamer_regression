from __future__ import print_function
import argparse
import os
import sys
import re
import logging
import logging.config
from os import listdir
from os.path import isfile, isdir, join

import script.girder_handler as gh
import script.run_gamer as gamer

current_path = os.getcwd()

#over all global variable
gamer.gamer_abs_path = '/work1/xuanshan/gamer'

#grep all tests we have
test_example_path = [gamer.gamer_abs_path + '/example/test_problem/Hydro/', gamer.gamer_abs_path + '/example/test_problem/ELBDM/']

all_tests = {}
for directory in test_example_path:
	for direc in listdir(directory):
		all_tests[direc]=directory+direc

#Cover all_tests for the testing usage
#Needs to be remove after release
all_tests = {
	'Riemann'     :'/work1/xuanshan/gamer/example/test_problem/Hydro/Riemann',
	'BlastWave'   :'/work1/xuanshan/gamer/example/test_problem/Hydro/BlastWave',
	'AcousticWave':'/work1/xuanshan/gamer/example/test_problem/Hydro/AcousticWave',
	'Plummer'     :'/work1/xuanshan/gamer/example/test_problem/Hydro/Plummer'
		}

#set up index of tests
test_index = []
for t in all_tests:
	test_index.append(t)
		
#init global logging variable
file_name = 'test.log'
if isfile(file_name):
	os.remove(file_name)

std_formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
save_formatter = logging.Formatter('%(levelname)-8s %(name)-15s %(message)s')
ch = logging.StreamHandler()
file_handler = logging.FileHandler(file_name)

####################################################################
##                         get arguments                          ##
####################################################################
args = {'error_level': 'level0'}
testing_tests = {}
if len(sys.argv) > 1:
	for ind_arg in range(len(sys.argv)):
		if   '-error-level' in sys.argv[ind_arg]:
			args['error_level'] = sys.argv[ind_arg+1]
		elif '-p' in sys.argv[ind_arg] or '--path' in sys.argv[ind_arg]:
			gamer.abs_path = sys.argv[ind_arg+1]
		elif '-t' in sys.argv[ind_arg] or '--test' in sys.argv[ind_arg]:
			its = re.split(',',sys.argv[ind_arg+1])
			for ind in its:
				testing_tests[test_index[int(ind)]]=all_tests[test_index[int(ind)]]
		elif '-h' in sys.argv[ind_arg] or '--help' in sys.argv[ind_arg]:
			print('usage: python regression_test.py')
			print('Options:')
			print('\t-error_level\tError allows in this test."level0" or "level1". Default: "level0"')
			print('\t-p --path\tSet the path of gamer path.')
			print('\t-t --test\tSpecify tests to run. Tests should be saperated by "," Default: all tests')
			print('\t-h --help\tUsage and option list')
			print('Test index:')
			for i in range(len(test_index)):
				print("\t%i\t%s"%(i,test_index[i]))
			quit()
if len(testing_tests) == 0:
	testing_tests = all_tests
####################################################################

def log_init():
	#set up log  config
	logging.basicConfig(level=0)
	#add log config into std output
	ch.setLevel(logging.DEBUG)	
	ch.setFormatter(std_formatter)
	#add log config into file
	file_handler.setLevel(0)
	file_handler.setFormatter(save_formatter)

def set_up_logger(logger):
	#set up settings to logger object
	logger.setLevel(logging.DEBUG)
	logger.propagate = False
	logger.addHandler(ch)
	logger.addHandler(file_handler)

test_logger = logging.getLogger('regression_test')
set_up_logger(test_logger)

def main(tests):
	#set tests to run.
	for test_name in tests:
		indi_test_logger = logging.getLogger(test_name)
		set_up_logger(indi_test_logger)
		indi_test_logger.info('Test %s start' %(test_name))
		#try:
	#set up gamer make configuration
		config_folder = '/work1/xuanshan/gamer/regression_teset/tests/%s' %(test_name)
		config, input_settings = gamer.get_config(config_folder + '/configs')
	#make gamer
		#try:
		indi_test_logger.info('Start compiling gamer')
		Fail = gamer.make(config,logger=indi_test_logger)
		if Fail == 1:
			continue
		#except Exception:
		#	test_logger.error('Compile_error', exc_info=True)
	#run gamer
		#try:
	#prepare to run gamer
		Fails = []
		test_folder = tests[test_name]
	#run gamer in different Input__Paramete	
		indi_test_logger.info('Start running test')
		for input_setting in input_settings:
			gamer.copy_example(test_folder,test_name +'_'+ input_setting)
			gamer.set_input(input_settings[input_setting])
	#run gamer
			Fail = gamer.run(logger=indi_test_logger,input_name=input_setting)
			if Fail == 1:
				Fails.append(input_setting)
		#except Exception:
		#	indi_test_logger.error('Run_error')
	#analyze
		indi_test_logger.info('Start data analyze')
		gamer.analyze(test_name,Fails)
	#compare result and expect
		#try:
		#download compare file
		gh.download_test_compare_data(test_name,config_folder)
		#compare file
		gamer.make_compare_tool(test_folder,config)
		indi_test_logger.info('Start Data_compare data consistency')
		gamer.check_answer(test_name,Fails,logger=indi_test_logger,error_level=args['error_level'])
		
		#except Exception:
		#	test_logger.debug('Check script error')

		#except Exception:
		#	test_logger.error('Exception occurred', exc_info=True)
		#	pass
		indi_test_logger.info('Test %s end' %(test_name))
	test_logger.info('Test done.')

def test_result(all_tests):
	#check failure during tests
	log_file = open('%s/test.log'%(current_path))
	log = log_file.readlines()
	error_count = 0
	test_debug = {}
	for t in all_tests:
		test_debug[t] = {}
	fail_test = {}
	for line in log:
		if 'INFO' in line:
			if 'Start' in line:
				array = re.split('\s*',line)
				name = array[1]
				stage = array[3]
				test_debug[name][stage]=[]
			continue
		elif 'DEBUG' in line:
			test_debug[name][stage].append(line[25:])
			continue
		elif 'ERROR' in line:
			if not 'regression_test' in line:
				array = re.split('\s*',line)
				testname = array[1]
				if not testname in fail_test:
					fail_test[testname] = []
				fail_test[testname].append(array[2])
		elif 'WARNING' in line:
			if not 'regression_test' in line:
				array = re.split('\s*',line)
				testname = array[1]
				if not testname in fail_test:
					fail_test[testname] = []
			#if 'ERROR' in line:
				fail_test[testname].append(array[2])
	#summary test results
	print('\nTest Result')
	if len(fail_test) > 0:
			print('%i tests done. %i test failed.'%(len(all_tests),len(fail_test)))
	else:
		print('%i tests done. Test passed.'%(len(all_tests)))
	for test in all_tests:
		if test in fail_test:
			print('%s : Failed'%(test))
			print('\tFail stage:')
			for fail_stage in fail_test[test]:
				print('\t\t%s'%fail_stage)
				print('\tError message:')
				for errorline in test_debug[test][fail_stage]:
					print('\t\t%s'%errorline)
		else:
			print('%s : Passed'%(test))

if __name__ == '__main__':
	log_init()
	try:
		test_logger.info('Test start.')
		main(testing_tests)
	except Exception:
		test_logger.critical('',exc_info=True)
		raise
	test_result(testing_tests)
