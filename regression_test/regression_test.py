from __future__ import print_function
import argparse
import os
import sys
import logging
import logging.config
from os import listdir
from os.path import isfile, isdir, join

import script.run_gamer as gamer

current_path = os.getcwd()

#over all global variable
gamer.gamer_abs_path = '/work1/xuanshan/gamer'
if len(sys.argv)>1:
	gamer.gamer_abs_path = sys.argv[1]

#grep all tests we have
test_example_path = [gamer.gamer_abs_path + '/example/test_problem/Hydro/', gamer.gamer_abs_path + '/example/test_problem/ELBDM/']

all_tests = {}
for directory in test_example_path:
	for direc in listdir(directory):
		all_tests[direc]=directory+direc

testing_tests = {'AcousticWave':'/work1/xuanshan/gamer/example/test_problem/Hydro/AcousticWave'}

#init global logging variable
file_name = 'test.log'

std_formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
save_formatter = logging.Formatter('%(levelname)-8s %(name)-15s %(message)s')
ch = logging.StreamHandler()
file_handler = logging.FileHandler(file_name)

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
		#try:
	#set up gamer make configuration
		config, input_settings = gamer.get_config('/work1/xuanshan/regression_test/configs/%s'%(test_name))
	#make gamer
		#try:
		gamer.make(config,logger=indi_test_logger)
		#except Exception:
		#	test_logger.error('Compile_error', exc_info=True)
	#run gamer
		#try:
	#prepare to run gamer
		test_folder = tests[test_name]
	#run gamer in different Input__Parameter
		for input_setting in input_settings:
			gamer.copy_example(test_folder,test_name +'_'+ input_setting)
			gamer.set_input(input_settings[input_setting])
	#run gamer
			gamer.run(logger=indi_test_logger)
		#except Exception:
		#	indi_test_logger.error('Run_error')
	#analyze

	#compare result and expect
		#try:
			answer_check_result = gamer.check_answer([1],[1],logger=indi_test_logger)
			if not answer_check_result:
				indi_test_logger.error('Answer_wrong')
		#except Exception:
		#	test_logger.debug('Check script error')

		#except Exception:
		#	test_logger.error('Exception occurred', exc_info=True)
		#	pass
	test_logger.info('Test done.')

def test_result():
	#check failure during tests
	log_file = open('%s/test.log'%(current_path))
	log = log_file.readlines()
	error_count = 0
	fail_test = {}
	for line in log:
		if not 'regression_test' in line:
			testname = line[9:24]
			if not testname in fail_test:
				fail_test[testname] = []
		#if 'ERROR' in line:
			fail_test[testname].append(line[25:])
	#summary test results
	if len(fail_test) > 0:
		print('%i tests done. %i test failed.'%(len(testing_tests),len(fail_test)))
		for ft in fail_test:
			print('Fail test: %s'%(ft))
			print('Fail stage:')
			for fail_stage in fail_test[ft]:
				print(fail_stage)
	else:
		print('%i tests done. Test passed.'%(len(testing_tests)))

if __name__ == '__main__':
	log_init()
	try:
		test_logger.info('Test start.')
		main(testing_tests)
	except Exception:
		test_logger.critical('',exc_info=True)
		raise
	test_result()
