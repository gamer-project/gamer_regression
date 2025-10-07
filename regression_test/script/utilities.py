"""
Please arrange the functions and classes alphabetically.
"""
import os
import subprocess
import time
import yaml
import six
from contextlib import contextmanager


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


def read_yaml(file_name):
    """
    Read the yaml file.

    Inputs
    ------
    file_name : str
       File name.
    """
    with open(file_name) as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader if six.PY3 else yaml.Loader)

    return data


def priority2int(priority: int | str) -> int:
    if isinstance(priority, int):
        if priority >= 0:
            return priority
        else:
            raise ValueError(f"Integer priority must be non-negative, got {priority}.")
    elif isinstance(priority, str):
        PRIORITY_MAP = {"high": 30, "medium": 20, "low": 10}
        if priority.lower() in PRIORITY_MAP:
            return PRIORITY_MAP[priority.lower()]
        elif priority.isdigit() and int(priority) >= 0:
            return int(priority)
        else:
            raise ValueError(
                f"Invalid string priority: '{priority}'. Must be 'high', 'medium', 'low', or a non-negative integer.")
    else:
        raise ValueError(f"Priority must be an integer or string, got {type(priority)}.")


@contextmanager
def time_step(step_name: str, timing_dict: dict, logger=None):
    """Context manager for timing test steps with automatic logging.

    Parameters
    ----------
    step_name : str
        Name of the step being timed (will be used as key in timing_dict)
    timing_dict : dict
        Dictionary to store the timing result
    logger : logging.Logger, optional
        Logger to output timing information

    Yields
    ------
    None
        Context for the timed operation

    Examples
    --------
    >>> timing = {}
    >>> with time_step('compile', timing, logger):
    ...     # do something
    ...     pass
    >>> print(timing['compile'])  # prints elapsed time in seconds
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        timing_dict[step_name] = elapsed
        if logger:
            logger.info(f"Step '{step_name}' took {elapsed:.3f} seconds")
