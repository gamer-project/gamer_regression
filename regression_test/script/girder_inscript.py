####################################################################################################
# Imports
####################################################################################################
import girder_client
import yaml
import six
import os
import sys
import datetime
import subprocess
import getpass

# Prevent generation of .pyc files
# This should be set before importing any user modules
sys.dont_write_bytecode = True

from script.utilities import check_dict_key, read_yaml, gen2dict



####################################################################################################
# Global variables
####################################################################################################
RETURN_SUCCESS = 0
RETURN_FAIL    = 1

API_URL       = 'https://girder.hub.yt/api/v1'
API_KEY       = 'REMOVED_API_KEY'
REG_FOLDER_ID = '6123170168085e0001634586'       # ID of /user/xuanweishan/gamer_regression_test

# Girder client
GC = girder_client.GirderClient( apiUrl=API_URL )
GC.authenticate( apiKey=API_KEY )

HOME_FOLDER_DICT = gen2dict( GC.listFolder(REG_FOLDER_ID) )



####################################################################################################
# Functions
####################################################################################################
def item_id_list( girder_dict ):
    """
    Convert the girder dict to cleaner version

    Returns
    -------

    id_list : dict
       A dictionary of id access with file name.
    """
    id_list = {}
    for key in girder_dict:
        id_list[key] = girder_dict[key]['_id']

    return id_list


def get_latest_version( test_name, gamer_abs_path ):
    """
    Get the latest upload time of the latest reference data.

    Parameters
    ----------

    test_name      : string
       The name of the test problem.
    gamer_abs_path : string
       The absoulte path of gemer directory.

    Returns
    -------

    ver['time']    : int
       The upload time of the latest version.
    """
    comp_list_file = gamer_abs_path + '/regression_test/compare_version_list/compare_list'
    ver_list = read_yaml( comp_list_file )

    ver = {'time':0,'inputs':[]}
    for version in ver_list[test_name]:
        if int(ver_list[test_name][version]['time']) <= ver['time']:    continue
        ver['time'] = int(ver_list[test_name][version]['time'])
        ver['inputs'] = ver_list[test_name][version]['members']

    return ver


def download_data( test_name, gamer_path, test_folder, **kwargs ):
    """
    Download the data from hub.yt

    Inputs
    ------

    Returns
    -------
    """
    check_dict_key( 'logger', kwargs, 'kwargs' )
    logger = kwargs['logger']

    ver_latest = get_latest_version( test_name, gamer_path )
    time       = ver_latest['time']
    inputs     = ver_latest['inputs']

    download_list = test_folder + '/compare_results'
    download_dict = read_yaml( download_list )
    test_folder_dict = {}

    # 1. Download the data
    for key in download_dict['identical']:
        d_path   = gamer_path + "/" + download_dict['identical'][key]['expect']
        d_temp   = d_path.split('/')
        d_folder = d_temp[-2] + '-' + str(time) # the folder of the file to be downloaded
        d_file   = d_temp[-1]                   # the file to be downloaded

        # store the folder information
        if d_folder not in test_folder_dict:
            try:
                test_folder_dict[d_folder] = gen2dict( GC.listItem( HOME_FOLDER_DICT[d_folder]['_id']) )
            except:
                logger.error( "Can not get the info of (name: %s, id: %s)!"%(d_folder, HOME_FOLDER_DICT[d_folder]['_id']) )
                return RETURN_FAIL

        file_id = test_folder_dict[d_folder][d_file]['_id']

        target_folder = "/".join(d_temp[:-1])   # download destination
        if not os.path.isdir(target_folder): os.makedirs(target_folder)

        # download
        try:
            logger.info( "Downloading (name: %s/%s, id: %s) --> %s"%(d_folder, d_file, file_id, target_folder) )
            GC.downloadItem( file_id, target_folder ) # Download a single file
            logger.info( "Finish Downloading" )
        except:
            logger.error( "Download (name: %s/%s, id: %s) fail!"%(d_folder, d_file, file_id) )
            return RETURN_FAIL

    # 2. Download the Record__*
    for sub_test_folder in test_folder_dict:
        for sub_file in test_folder_dict[sub_test_folder]:
            file_name = test_folder_dict[sub_test_folder][sub_file]['name']

            if "Record" not in file_name: continue

            file_id = test_folder_dict[sub_test_folder][sub_file]['_id']

            target_folder = gamer_path + "/regression_test/tests/" + test_name + "/" + sub_test_folder.split('-')[0]    # download destination

            # download
            try:
                logger.info( "Downloading (name: %s/%s, id: %s) --> %s"%(sub_test_folder, file_name, file_id, target_folder) )
                GC.downloadItem( file_id, target_folder ) # Download a single file
                logger.info( "Finish Downloading" )
            except:
                logger.error( "Download (name: %s/%s, id: %s) fail!"%(sub_test_folder, file_name, file_id) )
                return RETURN_FAIL

    return RETURN_SUCCESS


def download_compare_version_list( gamer_path, **kwargs ):
    check_dict_key( 'logger', kwargs, 'kwargs' )
    logger = kwargs['logger']

    folder_id = HOME_FOLDER_DICT['compare_version_list']['_id']
    target_folder = gamer_path + '/regression_test/compare_version_list'

    if not os.path.isdir(target_folder): os.makedirs(target_folder)

    try:
        logger.info( "Downloading compare_version_list" )
        GC.downloadFolderRecursive( folder_id, target_folder ) # This only download the files inside the folder
        logger.info( "Finish Downloading" )
    except:
        logger.error( "Download compare_version_list fail! id: %s"%(folder_id) )
        return RETURN_FAIL

    return RETURN_SUCCESS


def upload_data(test_name, gamer_path, test_folder, **kwargs):
    check_dict_key('logger', kwargs, 'kwargs')
    logger = kwargs['logger']
    
    item = os.path.basename(test_folder)
    compare_result_path = test_folder + '/compare_results'
    compare_list_path = gamer_path + '/regression_test/compare_version_list/compare_list'

    current_time = datetime.datetime.now().strftime('%Y%m%d%H%M')

    # 0. Set up gc for upload files
    api_key = getpass.getpass("Enter the api key:")

    gc = girder_client.GirderClient( apiUrl=API_URL )
    gc.authenticate( apiKey=api_key ) 

    logger.info("Upload new answer for test %s" %(test_name))

    # 1. Read the compare_list to get files to be upload
    compare_list = read_yaml(compare_list_path)
    latest_version_n = len(compare_list[test_name])
    next_version_n = latest_version_n + 1
    inputs = compare_list[test_name]['version_%i' %(latest_version_n)]['members']

    for n_input in inputs:
        # 2. Create folder with name connect to date and test name
        folder_to_upload = "%s/%s_%s-%s" %(test_folder, test_name, n_input, current_time)
        os.mkdir(folder_to_upload)

        # 3. Copy the data form source to prepared folder
        files = read_yaml(compare_result_path)['identical']
        for file_name in files:
            source_file = "%s/%s" %(gamer_path, files[file_name]['result'])
            if n_input == file_name.split('_')[0]:
                logger.info('Copying the file to be upload: %s ---> %s'%(source_file, folder_to_upload))
                try:
                    subprocess.check_call(['cp', source_file, folder_to_upload])
                except:
                    logger.error('Copying error. Stop upload process.')
                    logger.error('Please check the source: %s and target: %s'%(files[file_name]['expect'],folder_to_upload))
                    subprocess.check_call(['rm','-rf',folder_to_upload])
                    return RETURN_FAIL
            else: continue

        # 4. Upload folder to hub.yt
        try:
            logger.info('Start upload the folder %s' %folder_to_upload)
            gc.upload(folder_to_upload, REG_FOLDER_ID)
        except:
            logger.error("Upload new answer fail.")
            return RETURN_FAIL

    # 5. Update compare_list
    logger.info("Update the compare_list")
    version_name = 'version_%i' %(next_version_n)
    compare_list[test_name][version_name] = {
        'members' : inputs.copy(),
        'time'    : current_time,
    }
    with open(compare_list_path,'w') as stream:
        yaml.dump(compare_list, stream, default_flow_style=False)

    # 6. Upload compare_list
    logger.info("Upload new compare_list")
    if upload_compare_version_list(gc, gamer_path, **kwargs) == RETURN_FAIL:
        logger.error("Error while uploading the compare_list")
        return RETURN_FAIL
    return RETURN_SUCCESS


def upload_compare_version_list(gc, gamer_path, **kwargs):
    check_dict_key('logger', kwargs, 'kwargs')
    logger = kwargs['logger']

    local_file = gamer_path + '/regression_test/compare_version_list/compare_list'
    item = os.path.basename(local_file)
    target_dict_id = "6124affa68085e0001634618"
    target_dict = gen2dict(gc.listItem(target_dict_id))
    if item in target_dict:
        logger.debug("File 'compare_list' is already exist, old one will be covered.")
        parent_id = target_dict[item]['_id']
        gc.uploadFileToItem(parent_id, local_file)
    else:
        logger.debug("File 'compare_list' not exist, upload to the folder.")
        parent_id = target_dict_id
        gc.uploadFileToFolder(parent_id, local_file)
    logger.info("Upload compare_list finish")
    return RETURN_SUCCESS


####################################################################################################
# Main
####################################################################################################
if __name__ == '__main__':
    import logging

    HOME_FOLDER_DICT = gen2dict( GC.listFolder(REG_FOLDER_ID) )
    gen = GC.listFolder( REG_FOLDER_ID )
    home_folder = gen2dict( gen )

    #print(home_folder['AcousticWave_input4-202309110400'])

    #gen = GC.listItem( home_folder['AcousticWave_input4-202309110400']['_id'])

    #acoustic_folder = gen2dict( gen )
    #acoustic_dict = item_id_list( acoustic_folder )
    #print(acoustic_dict)
    #GC.downloadItem( '64fec3465545e01fe3479274', './' ) # Download a single file
    #GC.downloadFolderRecursive( '64f1b8025545e01fe347925b', './' ) # This only download the files inside the folder
    print("Test for upload data function")
    logging.basicConfig(level=0)
    logger = logging.getLogger("Inscript_test_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    

    test_name = "Riemann"
    gamer_path = "/work1/xuanshan/reg_sandbox/gamer"
    test_folder = gamer_path + "/regression_test/tests/Riemann"
    upload_data(test_name, gamer_path, test_folder,logger=logger)

