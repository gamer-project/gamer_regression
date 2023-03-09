import subprocess
import os
from os.path import isfile, isdir
import sys
import datetime
import six
import yaml
import logging

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

import script.run_gamer as gamer



####################################################################################################
# Global variables
####################################################################################################
apiUrl='https://girder.hub.yt/api/v1'
apiKey='REMOVED_API_KEY'
parent_folder = '/user/xuanweishan/gamer_regression_test'

girder_path = '/usr/local/bin/girder-cli'  # This should be modified by user.



####################################################################################################
# Functions
####################################################################################################
def load_latest_list():
    """

    Returns
    -------
    
    version_list     :
    latest_list_path :
    """
    #list all version files
    list_list_folder = gamer.gamer_abs_path + '/regression_test/compare_version_list'
    for root, dirs, files in os.walk(list_list_folder):
        list_list = files
        
    #find the latest version file
    latest = '0'
    for f in list_list:
        if int(latest.split('_')[-1]) <= int(f.split('_')[-1]):
            latest = f
    #load latest version file
    latest_list_path = gamer.gamer_abs_path + '/regression_test/compare_version_list/' + latest
    with open(latest_list_path,'r') as stream:
        version_list = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)
    return version_list, latest_list_path



####################################################################################################
# Download functions
####################################################################################################
def download_folder( hub_yt_folder_name, local_folder, **kwargs ):
    """
    Download all files in a hub.yt folder to local folder with girder-cli command.

    Parameters
    ----------

    hub_yt_folder_name : string
       Download target folder.
    local_folder       : string 
       Download local folder.
    kwargs             : 
       logger : class logger.Logger
          The logger of grider.

    Returns
    -------
    
    status             : int(0/1)
       The status of the function.(0: success)

    """
    status = 0
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(download_folder.__name__) )

    target_folder = parent_folder + hub_yt_folder_name

    command = [ girder_path, '--api-url', apiUrl, '--api-key', apiKey, \
                'download', '--parent-type', 'folder', target_folder, local_folder]

    logger.info('Downloading the folder: %s ---> %s' %(target_folder, local_folder))
    try:
        subprocess.check_call(command)
        logger.info('Download completed.')
    except subprocess.CalledProcessError as err:
        logger.error('Download error while downloading folder %s' %(hub_yt_folder_name))
        status = 1
    
    return status



def download_compare_version_list( **kwargs ):
    """
    Download the version manage files to local.

    Parameters
    ----------

    kwargs: 
       logger : class logger.Logger
          The logger of grider.
    
    Returns
    -------
    
    status             : int(0/1)
       The status of the function.(0: success)

    """
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(download_compare_version_list.__name__) )
    
    yt_folder_name = '/compare_version_list'
    local_folder   = gamer.gamer_abs_path + '/regression_test/compare_version_list'
    
    status = download_folder( yt_folder_name, local_folder, logger=logger )

    return status 



def get_latest_expect_version( test_name, version_list ):
    """
    Get the latest version of the reference data.

    Parameters
    ----------

    test_name    : string
       The name of the test problem.
    version_list : dict  
       All the available verison.

    Returns
    -------

    ver          : dict
       The latest version.
    """
    ver = {'time':0,'inputs':[]}
    for version in version_list[test_name]:
        if int(version_list[test_name][version]['time']) <= ver['time']:    continue
        ver['time'] = int(version_list[test_name][version]['time'])
        ver['inputs'] = version_list[test_name][version]['members']
    
    return ver



def download_test_compare_data( test_name, local_folder, version='latest', **kwargs ):
    """
    Download the reference data of the test.

    Parameters
    ----------

    test_name    : string
       Name of the test.
    local_folder : string
       The directory of the config folder.
    version      : string
       The version to be compared.
    kwargs       :
       logger : class logger.Logger
          The logger of grider.

    Returns
    -------
    
    all_status   : int(0/1)
       The status of the function.(0: success)

    """
    all_status = 0
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(download_folder.__name__) )
    
    #1. Load data_list
    version_list, version_list_name = load_latest_list()
    if not test_name in version_list:
        logger.debug('No data stored in hub.yt')
        return 1

    #2. Get data folder path in hub.yt of the version we need from data_list
    latest_ver = get_latest_expect_version( test_name, version_list )
    for Ninput in latest_ver['inputs']:
        latest_yt_path = '/%s_%s-%i'%(test_name,Ninput,latest_ver['time'])
        
        #3. Create local folders for each input settings
        local_folder_name = local_folder + '/%s_%s' %(test_name,Ninput)
        if not isdir(local_folder_name):
            os.mkdir(local_folder_name)
        
        #4. Download compare datas
        status = download_folder( latest_yt_path, local_folder_name, logger=logger )
        if status != 0:    all_status = status
    
    return all_status



####################################################################################################
# Upload functions
####################################################################################################
def upload_folder( target_folder, local_folder, **kwargs ):
    """
    Upload the folder.

    Parameters
    ----------
    
    target_folder : string
       Upload location.
    local_folder  : string
       Folder to be uploaded.
    kwargs        :
       logger : class logger.Logger
          The logger of grider.
    
    Returns
    -------
    
    status             : int(0/1)
       The status of the function.(0: success)
    """
    status = 0
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(upload_folder.__name__) )
    
    #target_folder = test_folder_Path
    command = [ girder_path, '--api-url', apiUrl, '--api-key', apiKey, \
                'upload', '--parent-type', 'folder', target_folder, local_folder ]
    
    kwargs['logger'].info( 'Uploading:  %s ---> %s'%(local_folder, target_folder) )
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as err:
        kwargs['logger'].error('upload_file error in %s' %(local_folder))
        status = 1
    
    return status



def create_upload_version_file( compare_list_file_name, test_name, new_folder_names, **kwargs ):
    """

    Parameters
    ----------
    
    compare_list_file_name : string

    tset_name              : string

    new_folder_names       : string

    kwargs                 :
       must include logger

    Returns
    -------
    
    status             : int(0/1)
       The status of the function.(0: success)

    """
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(create_upload_version_file.__name__) )
    
    with open(compare_list_file_name) as stream:
        old_compare_list = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)
    
    #find the name of current latest version name
    latest_ver = 'version_0'
    if test_name in old_compare_list:
        for ver in old_compare_list[test_name]:
            if int(ver.split('_')[-1]) > int(latest_ver.split('_')[-1]):
                latest_ver = ver
    
    #Create latest version informations
    #version name
    new_version_name = '%s_%i'%(latest_ver.split('_')[0],int(latest_ver.split('_')[-1])+1)
    #version time
    new_version_time = new_folder_names[0].split('-')[-1]
    #new version file name
    new_version_file_name = 'compare_list_%i' %(int(compare_list_file_name.split('_')[-1])+1)
    #inputs
    inputs = []
    for test_name_folder in new_folder_names:
        inputs.append(test_name_folder.split('-')[0].split('_')[-1])
    
    if not test_name in old_compare_list:
        old_compare_list[test_name] = {}
    old_compare_list[test_name][new_version_name] = {'time':new_version_time,'members':inputs}
    
    with open(new_version_file_name,'w') as stream:
        yaml.dump(old_compare_list,stream,default_flow_style=False)

    status = upload_folder(parent_folder+'/compare_version_list',new_version_file_name,logger=kwargs['logger'])

    return status



def upload_test_compare_data( test_name, source_folders, **kwargs ):
    """
    
    Parameters
    ----------

    test_name: string
       The name of the test.
    source_folders: string
       The upload target folders.
    kwargs:
       logger : class logger.Logger
          The logger of grider.
    
    Returns
    -------
    
    all_status    : int(0/1)
       The status of the function.(0: success)
    """
    all_status = 0
    try:
        logger = kwargs['logger']
    except:
        exit("logger is not passed into %s."%(upload_test_compare_data.__name__) )
    
    #1. Load compare list
    result_compare_list = gamer.gamer_abs_path + '/regression_test/tests/' + test_name + '/' + 'compare_results'
    with open(result_compare_list,'r') as stream:
        compare_list = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)
    
    #2. Create folder with name connect to date and test name
    up_date_folders = []
    current_time = datetime.datetime.now().strftime('%Y%m%d%H%M')
    for source_folder in source_folders:
        source_folder_name = os.path.basename(source_folder)
        folder_name = gamer.gamer_abs_path + '/regression_test/tests/' + test_name + '/' + source_folder_name + '-' + current_time
        os.mkdir(folder_name)
        up_date_folders.append(folder_name)
    
        #Copy files which wait for upload to a folder
        input_name = source_folder.split('_')[1]
        copy_cmds = []
        for mode in ['identicle']:
            for f in compare_list[mode]:
                file_path = gamer.gamer_abs_path + '/' + compare_list[mode][f]['result']
                copy_cmds.append(['cp', file_path, folder_name])
        try:
            for copy_cmd in copy_cmds:
                subprocess.check_call(copy_cmd)
        except:
            kwargs['logger'].error('Error on copy result file.')
            return 1
        #upload the whole folder to hub.yt
        status = upload_folder(parent_folder,folder_name,logger=kwargs['logger'])
        if status != 0: all_status = status

    latest_list, latest_list_name = load_latest_list()
    status = create_upload_version_file(latest_list_name,test_name,up_date_folders,logger=kwargs['logger'])
    if status != 0: all_status = status

    return all_status



####################################################################################################
# Main execution
####################################################################################################
if __name__ == '__main__':
    #setting logger for test
    test_logger = logging.getLogger('test')
    logging.basicConfig(level=0)
    ch = logging.StreamHandler()
    std_formatter = logging.Formatter('%(asctime)s : %(levelname)-8s %(name)-15s : %(message)s')
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(std_formatter)
    test_logger.setLevel(logging.DEBUG)
    test_logger.propagete = False
    test_logger.addHandler(ch)

    folders_to_upload = [
        '/work1/xuanshan/gamer/bin/Plummer_input1'
        ]
    print('test start')
    upload_test_compare_data('Plummer',folders_to_upload,logger=test_logger)

    #download_test_compare_data('Riemann','.',logger=test_logger)
    #download_compare_version_list(logger=test_logger)

    print('test pass')
