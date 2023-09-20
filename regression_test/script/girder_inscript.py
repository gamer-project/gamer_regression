####################################################################################################
# Imports
####################################################################################################
import girder_client
import yaml
import six
import os
import sys

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



####################################################################################################
# Main
####################################################################################################
if __name__ == '__main__':
    HOME_FOLDER_DICT = gen2dict( GC.listFolder(REG_FOLDER_ID) )
    gen = GC.listFolder( REG_FOLDER_ID )
    home_folder = gen2dict( gen )

    #print(home_folder['AcousticWave_input4-202309110400'])

    gen = GC.listItem( home_folder['AcousticWave_input4-202309110400']['_id'])

    acoustic_folder = gen2dict( gen )
    acoustic_dict = item_id_list( acoustic_folder )
    print(acoustic_dict)
    #GC.downloadItem( '64fec3465545e01fe3479274', './' ) # Download a single file
    #GC.downloadFolderRecursive( '64f1b8025545e01fe347925b', './' ) # This only download the files inside the folder
