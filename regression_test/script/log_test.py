import logging
import os

def log_init():
	logger = logging.getLogger('test')

	logging.basicConfig(level=0)

	console = logging.StreamHandler()
	file_handler = logging.FileHandler('test')

	formatter = logging.Formatter('%(levelname)-8s: %(message)s')
	
	file_handler.setFormatter(formatter)
	console.setFormatter(formatter)
	
	logger.addHandler(console)

	logger.addHandler(file_handler)

	logger.propagate = False

	logger.debug('123')
	logger.debug('223')

if __name__ == '__main__':
	log_init()
