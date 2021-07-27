import subprocess
import os

test_folder_ID = '60dea1b268085e00010e9502'
test_folder_Path = '/user/xuanweishan/Riemann'
test_item_ID = '60dea1b568085e00010e9504'
target_folder = './Riemann'

apiUrl='https://girder.hub.yt/api/v1'
apiKey='REMOVED_API_KEY'

def check_test_files(test_name):
	return 0

def download_test_compare_data(test_name,local_folder, version='latest',**kwargs):
	target_folder = test_folder_Path

	command = ['girder-cli','--api-url',apiUrl,'--api-key',apiKey,'download','--parent-type','folder',target_folder,local_folder]
	try:
		subprocess.check_call(command)
	except subprocess.CalledProcessError as err:
		kwargs['logger'].error('download_file error in %s' %(test_name))
		return 0

def upload_test_compare_data(target_folder,file_path,**kwargs):
	target_folder = test_folder_Path
	command = ['girder-cli','--api-url',apiUrl,'--api-key',apiKey,'upload','--parent-type','folder',target_folder,file_path]
	
	try:
		subprocess.check_call(command)
	except subprocess.CalledProcessError as err:
		kwargs['logger'].error('upload_file error in %s' %(file_path))
		return 0


if __name__ == '__main__':
	download_test_compare_data('Riemann')
	print('test pass')
