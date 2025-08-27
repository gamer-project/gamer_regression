####################################################################################################
# Imports
####################################################################################################
import datetime
import getpass
import girder_client
import logging
import os
import subprocess
import yaml
from .utilities import STATUS, check_dict_key, gen2dict, read_yaml


####################################################################################################
# Global variables
####################################################################################################
API_URL = 'https://girder.hub.yt/api/v1'
API_KEY = os.environ.get("GAMER_API_KEY")
REG_FOLDER_ID = "64f1b5cd5545e01fe3479259"       # ID of /user/chunyenchen2019/regression_test


####################################################################################################
# Class
####################################################################################################
class girder_handler():
    def __init__(self, gamer_path, home_folder_dict={}):
        self.logger = logging.getLogger('girder_handler')
        self.gamer_path = gamer_path
        self.gc = girder_client.GirderClient(apiUrl=API_URL)

        self.gc.authenticate(apiKey=API_KEY)

        self.home_folder_dict = self.__get_folder_tree(REG_FOLDER_ID) if home_folder_dict == {} else home_folder_dict

    def download_file_by_id(self, file_id, target_folder):
        try:
            self.gc.downloadItem(file_id, target_folder)
        except:
            self.logger.error("Download id: %s to %s fail!" % (file_id, target_folder))
            return STATUS.DOWNLOAD
        return STATUS.SUCCESS

    def download_compare_version_list(self):

        folder_id = self.home_folder_dict['compare_version_list']['_id']
        target_folder = self.gamer_path + '/regression_test/compare_version_list'

        if not os.path.isdir(target_folder):
            os.makedirs(target_folder)

        self.logger.info("Downloading compare_version_list")
        try:
            self.gc.downloadFolderRecursive(folder_id, target_folder)  # This only download the files inside the folder
            self.logger.info("Finish Downloading")
        except:
            self.logger.error("Download compare_version_list fail! id: %s" % (folder_id))
            return STATUS.DOWNLOAD

        return STATUS.SUCCESS

    def get_latest_version(self, test_name):
        """
        Get the latest upload time of the latest reference data.

        Parameters
        ----------

        test_name      : string
           The name of the test problem.

        Returns
        -------

        ver['time']    : int
        The upload time of the latest version.
        """
        comp_list_file = self.gamer_path + '/regression_test/compare_version_list/compare_list'
        ver_list = read_yaml(comp_list_file)

        time_out = 0
        for version in ver_list[test_name]:
            cur_time = int(ver_list[test_name][version])
            if cur_time <= time_out:
                continue
            time_out = cur_time

        return {"time": time_out}

    def __get_folder_tree(self, folder_id):
        """
        Get the folder tree from yt.hub
        Parameters
        ----------
        folder_id      : string
            The ID correspond to the target folder.
        Returns
        -------
        dict_tree      : dict
            The dict described folder tree.
        """
        dict_tree = {}
        leaf_folder = gen2dict(self.gc.listFolder(folder_id))
        leaf_item = gen2dict(self.gc.listItem(folder_id))

        for item in leaf_item:
            dict_tree[item] = {"_id": leaf_item[item]["_id"]}

        for folder in leaf_folder:
            leaf_id = leaf_folder[folder]["_id"]
            dict_tree[folder] = {"_id": leaf_id}
            dict_tree[folder].update(self.__get_folder_tree(leaf_id))

        return dict_tree


####################################################################################################
# Functions
####################################################################################################
def upload_data(test_name, gamer_path, test_folder, **kwargs):
    check_dict_key('logger', kwargs, 'kwargs')
    logger = kwargs['logger']

    item = os.path.basename(test_folder)
    compare_result_path = test_folder + '/compare_results'
    compare_list_path = gamer_path + '/regression_test/compare_version_list/compare_list'

    current_time = datetime.datetime.now().strftime('%Y%m%d%H%M')

    # 0. Set up gc for upload files
    api_key = getpass.getpass("Enter the api key:")
    try:
        gc = girder_client.GirderClient(apiUrl=API_URL)
        gc.authenticate(apiKey=api_key)
    except:
        logger.error("Upload authentication fail.")
        return STATUS.UPLOAD

    logger.info("Upload new answer for test %s" % (test_name))

    # 1. Read the compare_list to get files to be upload
    compare_list = read_yaml(compare_list_path)
    latest_version_n = len(compare_list[test_name])
    next_version_n = latest_version_n + 1
    inputs = compare_list[test_name]['version_%i' % (latest_version_n)]['members']

    for n_input in inputs:
        # 2. Create folder with name connect to date and test name
        folder_to_upload = "%s/%s_%s-%s" % (test_folder, test_name, n_input, current_time)
        os.mkdir(folder_to_upload)

        # 3. Copy the data form source to prepared folder
        files = read_yaml(compare_result_path)['identical']
        for file_name in files:
            source_file = "%s/%s" % (gamer_path, files[file_name]['result'])
            if n_input == files[file_name]['result'].split('/')[1].split('_')[-1]:
                logger.info("Copying the file to be upload: %s ---> %s" % (source_file, folder_to_upload))
                try:
                    subprocess.check_call(['cp', source_file, folder_to_upload])
                except:
                    logger.error("Copying error. Stop upload process.")
                    logger.error("Please check the source: %s and target: %s" %
                                 (files[file_name]['expect'], folder_to_upload))
                    subprocess.check_call(['rm', '-rf', folder_to_upload])
                    return STATUS.FAIL
            else:
                continue

        # 4. Upload folder to hub.yt
        try:
            logger.info("Start upload the folder %s" % folder_to_upload)
            gc.upload(folder_to_upload, REG_FOLDER_ID)
        except:
            logger.error("Upload new answer fail.")
            return STATUS.UPLOAD

    # 5. Update compare_list
    logger.info("Update the compare_list")
    version_name = 'version_%i' % (next_version_n)
    compare_list[test_name][version_name] = current_time

    with open(compare_list_path, 'w') as stream:
        yaml.dump(compare_list, stream, default_flow_style=False)

    # 6. Upload compare_list
    logger.info("Upload new compare_list")
    if _upload_compare_version_list(gc, gamer_path, **kwargs) != STATUS.SUCCESS:
        logger.error("Error while uploading the compare_list")
        return STATUS.UPLOAD
    return STATUS.SUCCESS


def _upload_compare_version_list(gc, gamer_path, **kwargs):
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
    return STATUS.SUCCESS


####################################################################################################
# Main
####################################################################################################
if __name__ == '__main__':
    import logging

    GC = girder_client.GirderClient(apiUrl=API_URL)
    HOME_FOLDER_DICT = gen2dict(GC.listFolder(REG_FOLDER_ID))
    gen = GC.listFolder(REG_FOLDER_ID)
    home_folder = gen2dict(gen)

    # print(home_folder['AcousticWave_input4-202309110400'])

    # gen = GC.listItem( home_folder['AcousticWave_input4-202309110400']['_id'])

    # acoustic_folder = gen2dict( gen )
    # acoustic_dict = item_id_list( acoustic_folder )
    # print(acoustic_dict)
    # GC.downloadItem( '64fec3465545e01fe3479274', './' ) # Download a single file
    # GC.downloadFolderRecursive( '64f1b8025545e01fe347925b', './' ) # This only download the files inside the folder
    print("Test for upload data function")
    logging.basicConfig(level=0)
    logger = logging.getLogger("Inscript_test_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    test_name = "AcousticWave"
    gamer_path = "/work1/xuanshan/reg_sandbox/gamer"
    test_folder = gamer_path + "/regression_test/tests/" + test_name
    upload_data(test_name, gamer_path, test_folder, logger=logger)
