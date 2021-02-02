from __future__ import print_function
import argparse
import os
import logging
import logging.config
from pkgutil import iter_modules

import script.run_gamer as gamer
#over all global variable
gamer.gamer_abs_path = '/work1/xuanshan/gamer_test'

#grep all tests we have
test_example_path = [gamer.gamer_abs_path + '/example/test_problem/Hydro/', gamer.gamer_abs_path + '/example/test_problem/ELBDM']
all_tests = []
for _,pk,tf in iter_modules(test_example_path):
	all_tests.append(pk)

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

def main():
#set tests to run.
	tests = ['Riemann',]
	for test_name in tests:
		try:
#set up gamer make configuration
			config = gamer.get_config('/work1/xuanshan/regression_test/make_config')
#make gamer
			try:
				make_logger = logging.getLogger('make_%s'%(test_name))
				set_up_logger(make_logger)
				gamer.make(config,logger=make_logger)
			except Exception:
				make_logger.error('Compile error occurred', exc_info=True)
#run gamer
			try:
#prepare to run gamer
				run_logger = logging.getLogger('run_%s'%(test_name))
				set_up_logger(run_logger)
				test_folder = gamer.gamer_abs_path + '/example/test_problem/Hydro/' + test_name
				gamer.copy_example(test_folder)
#run
				gamer.run(logger=run_logger)
			except Exception:
				run_logger.error('Run error occurred')


		except Exception:
			test_logger.error('Exception occurred', exc_info=True)
			pass
#check failure during tests
	test_logger.info('Test done.')

if __name__ == '__main__':
	log_init()

	try:
		test_logger.info('Test start.')
		main()
	except Exception:
		test_logger.critical('',exc_info=True)
		raise
