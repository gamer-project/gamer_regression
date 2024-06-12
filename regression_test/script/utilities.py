"""
Please arrange the functions and classes alphabetically.
"""
import yaml
import six
import ctypes
import logging



####################################################################################################
# Class
####################################################################################################
class STATUS:
    SUCCESS      = 0
    FAIL         = 1
    MISSING_FILE = 2
    COMPILE_ERR  = 3
    EDITING_FAIL = 4
    EXTERNAL     = 5
    GAMER_FAIL   = 6
    DOWNLOAD     = 7
    UPLOAD       = 8
    COPY_FILES   = 9
    EDIT_FILE    = 10
    COMPARISON   = 11

    para_dict = locals().copy()
    CODE_TABLE   = [ "" for i in range(len(para_dict)) ]
    for name, value in para_dict.items():
        if name == "__module__": continue
        if name == "__qualname__": continue
        CODE_TABLE[value] = name




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


def get_gpu_arch():
    """
    Outputs some information on CUDA-enabled devices on your computer, including current memory usage.

    It's a port of https://gist.github.com/f0k/0d6431e3faa60bffc788f8b4daa029b1
    from C to Python with ctypes, so it can run without compiling anything. Note
    that this is a direct translation with no attempt to make the code Pythonic.
    It's meant as a general demonstration on how to obtain CUDA device information
    from Python without resorting to nvidia-smi or a compiled Python extension.

    Author: Jan Schluter
    License: MIT (https://gist.github.com/f0k/63a664160d016a491b2cbea15913d549#gistcomment-3870498)
    """
    CUDA_SUCCESS = 0
    libnames = ('libcuda.so', 'libcuda.dylib', 'cuda.dll')
    for libname in libnames:
        try:
            cuda = ctypes.CDLL(libname)
        except OSError:
            continue
        else:
            break
    else:
        raise OSError("could not load any of: " + ' '.join(libnames))

    nGpus, cc_major, cc_minor, device = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int()

    def cuda_check_error( result ):
        if result == CUDA_SUCCESS: return

        error_str = ctypes.c_char_p()

        cuda.cuGetErrorString(result, ctypes.byref(error_str))
        raise BaseException( "CUDA failed with error code %d: %s"%( result, error_str.value.decode() ) )

        return

    cuda_check_error( cuda.cuInit(0) )
    cuda_check_error( cuda.cuDeviceGetCount(ctypes.byref(nGpus)) )

    arch = ""
    if nGpus.value > 1: print("WARNING: More than one GPU. Selecting the last GPU architecture.")
    for i in range(nGpus.value):
        cuda_check_error( cuda.cuDeviceGet(ctypes.byref(device), i) )
        cuda_check_error( cuda.cuDeviceComputeCapability(ctypes.byref(cc_major), ctypes.byref(cc_minor), device) )

        # https://en.wikipedia.org/wiki/CUDA#GPUs_supported
        if cc_major.value == 1:
            arch = "TESLA"
        elif cc_major.value == 2:
            arch = "FERMI"
        elif cc_major.value == 3:
            arch = "KEPLER"
        elif cc_major.value == 5:
            arch = "MAXWELL"
        elif cc_major.value == 6:
            arch = "PASCAL"
        elif cc_major.value == 7 and cc_minor.value in [0, 2]:
            arch = "VOLTA"
        elif cc_major.value == 7 and cc_minor.value == 5:
            arch = "TURING"
        elif cc_major.value == 8 and cc_minor.value in [0, 6, 7]:
            arch = "AMPERE"
        elif cc_major.value == 8 and cc_minor.value == 9:
            arch = "ADA"
        elif cc_major.value == 9 and cc_minor.value == 0:
            arch = "HOPPER"
        else:
            raise BaseException("Undefined architecture in the script.")

    return arch


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

    return data


def read_test_config( test_names ):
    all_test_name_configs = {}
    all_test_types = []
    for name, path in test_names.items():
        config = read_yaml( path +'/configs')
        all_test_name_configs[name] = config
        for t_type in config:
            if t_type in all_test_types: continue
            all_test_types.append(t_type)

    return all_test_name_configs, all_test_types


def set_up_logger( logger_name, ch, file_handler ):
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
    logger = logging.getLogger( logger_name )
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(ch)
    logger.addHandler(file_handler)

    return logger
