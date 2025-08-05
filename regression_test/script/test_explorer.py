import os
from os.path import isfile
from .utilities import read_yaml
from .runtime_vars import RuntimeVariables


class TestExplorer:
    """
    A class for detecting Tests and return a list of tests satisfying the query.
    """

    def __init__(self, rtvars: RuntimeVariables, input_args):
        """
        Initialize the regression test.

        Inputs
        ------

        input_args   : dict
        A dictionary contains the regression parameters.

        Returns
        -------

        testing_test : list
        A list contains strings of test name which to be tested.
        """

        # 2. Test problem
        TEST_EXAMPLE_PATH = os.path.join(rtvars.gamer_path, 'regression_test', 'tests')
        # get the config dict of each test
        all_test_name = {direc: os.path.join(TEST_EXAMPLE_PATH, direc) for direc in os.listdir(TEST_EXAMPLE_PATH)}
        all_test_name.pop('Template')           # Remove the Template folder from test

        def read_test_config(test_names: dict):
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

        ALL_TEST_CONFIGS, all_type_name = read_test_config(all_test_name)
        NAME_INDEX = [n for n in all_test_name]
        TYPE_INDEX = all_type_name

        PRIOR = {"high": 3, "medium": 2, "low": 1}

        # 0. Setting the default test type
        if len(input_args["type"]) == 0:
            input_args["type"] = [i for i in range(len(TYPE_INDEX))]
        if len(input_args["name"]) == 0:
            input_args["name"] = [i for i in range(len(NAME_INDEX))]

        # 1. Check if the input arguments are valid.
        for idx_g in input_args["type"]:
            if idx_g < 0 or idx_g > len(TYPE_INDEX):
                raise IndexError("Unrecognize index of the test type: %d" % idx_g)

        for idx_n in input_args["name"]:
            if idx_n < 0 or idx_n >= len(NAME_INDEX):
                raise IndexError("Unrecognize index of the test name: %d" % idx_n)

        test_configs = {}
        for idx_t in input_args["type"]:
            for idx_n in input_args["name"]:
                test_name = NAME_INDEX[idx_n]
                test_type = TYPE_INDEX[idx_t]
                try:
                    test_priority = ALL_TEST_CONFIGS[test_name][test_type]["priority"]
                    if PRIOR[test_priority] < PRIOR[input_args["priority"]]:
                        continue
                    test_configs[test_name+"_"+test_type] = ALL_TEST_CONFIGS[test_name][test_type]
                    test_configs[test_name+"_"+test_type]["name"] = test_name
                    test_configs[test_name+"_"+test_type]["type"] = test_type
                except:
                    pass

        # 2. Store to global variables
        input_args["output"] += ".log"

        # 3. Remove the existing log file
        if isfile(input_args["output"]):
            print('WARNING!!! %s is already exist. The original log file will be removed.' % (input_args["output"]))
            os.remove(input_args["output"])

        self.test_configs = test_configs  # The dict contains "Problem_sub-problem"
        self.input_args = input_args
