"""
Please arrange the functions and classes alphabetically.
"""
import os
import subprocess
import yaml
import six
import ctypes
import logging


####################################################################################################
# Class
####################################################################################################
class STATUS:
    SUCCESS = 0
    FAIL = 1
    MISSING_FILE = 2
    COMPILE_ERR = 3
    EDITING_FAIL = 4
    EXTERNAL = 5
    GAMER_FAIL = 6
    DOWNLOAD = 7
    UPLOAD = 8
    COPY_FILES = 9
    EDIT_FILE = 10
    COMPARISON = 11

    para_dict = locals().copy()
    CODE_TABLE = ["" for i in range(len(para_dict))]
    for name, value in para_dict.items():
        if name == "__module__":
            continue
        if name == "__qualname__":
            continue
        CODE_TABLE[value] = name


####################################################################################################
# Functions
####################################################################################################
def check_dict_key(check_list, check_dict, dict_name):
    """
    Check if the key is exist in dict

    Inputs
    ------

    check_list : str or list of string
       Keys to be checked.
    check_dict : dict
       Dictionary to be checked.
    dict_name  : str
       The name of dictionary.
    """
    if type(check_list) != type([]):
        check_list = [check_list]

    for key in check_list:
        if key not in check_dict:
            raise BaseException("%s is not passed in %s." % (key, dict_name))

    return


def gen2dict(gen):
    """
    Transform generator to dictionary.

    Inputs
    ------

    gen      : generator
       Generator store dictionarys information.

    Return
    ------

    dict_out : dict
       Dictionary store the generator informaiton.

    """
    dict_out = {}
    while True:
        try:
            temp = next(gen)
            dict_out[temp['name']] = temp
        except:
            break

    return dict_out


def get_git_info(path):
    """
    Get the git folder HEAD hash.

    Inputs
    ------
    path        :
       path to git folder

    Returns
    -------

    commit_hash : str
       git folder HEAD hash
    """
    current_abs_path = os.getcwd()

    os.chdir(path)
    try:
        commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except:
        commit_hash = "UNKNOWN"
    os.chdir(current_abs_path)

    return commit_hash


def read_yaml(file_name, read_type=None):
    """
    Read the yaml file.

    Inputs
    ------
    file_name : str
       File name.
    read_type : str
       Read file type. [config/test_list]

    Returns
    -------

    config:
       data['MAKE_CONFIG']    : dict
          The config of the makefile.
       data['INPUT_SETTINGS'] : dict
          The config of the Input__Parameters.
    test_list:
       data                   : dict
          The test problems of each group.

    """
    with open(file_name) as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)

    return data


def read_test_config(test_names):
    all_test_name_configs = {}
    all_test_types = []
    for name, path in test_names.items():
        config = read_yaml(path + '/configs')
        all_test_name_configs[name] = config
        for t_type in config:
            if t_type in all_test_types:
                continue
            all_test_types.append(t_type)

    return all_test_name_configs, all_test_types


def set_up_logger(logger_name, ch, file_handler):
    """
    Set up settings to logger object

    Parameters
    ----------

    logger_name  : string
       The name of logger.
    ch           : class logging.StreamHandler
       Saving the screen output format to the logger.
    file_handler : class logging.FileHandler
       Saving the file output format to the logger.

    Returns
    -------

    logger       : class logger.Logger
       The logger added the file handler and the stream handler with logger_name.

    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(ch)
    logger.addHandler(file_handler)

    return logger
