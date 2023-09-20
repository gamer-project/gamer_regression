import os
import yaml
import six



####################################################################################################
# Functions
####################################################################################################
def check_dict_key( check_list, check_dict, dict_name ):
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
    if type(check_list) != type([]): check_list = [check_list]

    for key in check_list:
        if key not in check_dict: raise BaseException( "%s is not passed in %s."%(key, dict_name) )

    return


def read_yaml( file_name, read_type=None ):
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
    with open( file_name ) as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)

    if read_type == "config":
        return data['MAKE_CONFIG'], data['INPUT_SETTINGS']
    elif read_type in ["test_list", "compare_list"]:
        return data
    else:
        return data


def gen2dict( gen ):
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


