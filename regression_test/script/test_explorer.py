import os
from .utilities import read_yaml
from .runtime_vars import RuntimeVariables
from .models import TestProblem, TestType, TestCase, TestReference


PRIOR = {"high": 3, "medium": 2, "low": 1}


class TestExplorer:
    """Discover tests and expand to a flat list of TestCase units."""

    def __init__(self, rtvars: RuntimeVariables):
        TESTS_ROOT = os.path.join(rtvars.gamer_path, 'regression_test', 'tests')

        # Collect problem directories (exclude Template)
        problems = [d for d in os.listdir(TESTS_ROOT) if d != 'Template']

        # Build indices then honor CLI filters (by ordinal index)
        name_index = problems

        # Aggregate all type names to index map by scanning configs
        type_order: list[str] = []
        configs_by_problem: dict[str, dict] = {}
        for pname in problems:
            cfg = read_yaml(os.path.join(TESTS_ROOT, pname, 'configs'))
            configs_by_problem[pname] = cfg
            for tname in cfg.keys():
                if tname not in type_order:
                    type_order.append(tname)

        # Defaults if CLI did not specify
        if len(rtvars.type) == 0:
            rtvars.type = list(range(len(type_order)))
        if len(rtvars.name) == 0:
            rtvars.name = list(range(len(name_index)))

        # Validate indices
        for idx_t in rtvars.type:
            if idx_t < 0 or idx_t >= len(type_order):
                raise IndexError(f"Unrecognize index of the test type: {idx_t}")
        for idx_n in rtvars.name:
            if idx_n < 0 or idx_n >= len(name_index):
                raise IndexError(f"Unrecognize index of the test problem: {idx_n}")

        cases: list[TestCase] = []

        for idx_t in rtvars.type:
            type_name = type_order[idx_t]
            for idx_n in rtvars.name:
                problem_name = name_index[idx_n]
                cfg = configs_by_problem[problem_name]
                if type_name not in cfg:
                    continue
                t_cfg = cfg[type_name]
                # Priority gating
                if PRIOR.get(t_cfg.get('priority', 'high'), 1) < PRIOR.get(rtvars.priority, 1):
                    continue

                levels = t_cfg.get('levels', {})
                pre_scripts = t_cfg.get('pre_script', [])
                post_scripts = t_cfg.get('post_script', [])
                user_cmp = t_cfg.get('user_compare_script', [])

                # References: shared at type level; attached to each case
                refs_cfg = t_cfg.get('reference', [])
                refs = [TestReference(name=r['name'], loc=r['loc'], file_type=r['file_type']) for r in refs_cfg]

                for case_idx, case_cfg in enumerate(t_cfg.get('cases', [])):
                    test_case = TestCase(
                        problem_name=problem_name,
                        type_name=type_name,
                        case_index=case_idx,
                        makefile_cfg=case_cfg.get('Makefile', {}),
                        input_parameter=case_cfg.get('Input__Parameter', {}),
                        input_testprob=case_cfg.get('Input__TestProb', {}),
                        pre_scripts=pre_scripts.copy(),
                        post_scripts=post_scripts.copy(),
                        user_compare_scripts=user_cmp.copy(),
                        references=refs.copy(),
                        levels=levels.copy(),
                    )
                    cases.append(test_case)

        # Flat list of per-case units
        self.test_cases: list[TestCase] = cases
