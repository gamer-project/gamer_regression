import os
from typing import Dict, List, Optional
from .models import TestProblem, TestType, TestCase, TestReference
from .runtime_vars import RuntimeVariables
from .utilities import read_yaml


PRIOR = {"high": 3, "medium": 2, "low": 1}


class TestExplorer:
    """Load tests, validate schema, and provide filtered TestCase lists."""

    def __init__(self, rtvars: RuntimeVariables):
        self.rtvars = rtvars
        self.tests_root = os.path.join(rtvars.gamer_path, 'regression_test', 'tests')
        self.problems: List[str] = []
        self.type_order: List[str] = []
        self.raw_configs: Dict[str, dict] = {}
        self.problems_model: List[TestProblem] = []

        # Only load structures here; then validate/build models
        self._load()
        self._validate_and_build()

    def _load(self) -> None:
        # Collect problem directories (exclude Template)
        self.problems = [d for d in os.listdir(self.tests_root) if d != 'Template']

        # Load YAML per problem and record union of type names
        self.type_order = []
        self.raw_configs.clear()
        for pname in self.problems:
            cfg = read_yaml(os.path.join(self.tests_root, pname, 'configs'))
            self.raw_configs[pname] = cfg
            for tname in cfg.keys():
                if tname not in self.type_order:
                    self.type_order.append(tname)

    def _validate_and_build(self) -> None:
        """Validate raw YAML and build TestProblem/TestType/TestCase models."""
        allowed_prior = set(PRIOR.keys())
        allowed_ftypes = {"TEXT", "HDF5", "NOTE"}

        problems_model: List[TestProblem] = []
        for problem_name, cfg in self.raw_configs.items():
            problem = TestProblem(name=problem_name)
            for type_name, t_cfg in cfg.items():
                if not isinstance(t_cfg, dict):
                    raise ValueError(f"Config for {problem_name}/{type_name} must be a mapping")

                priority = t_cfg.get('priority', None)
                if priority not in allowed_prior:
                    raise ValueError(f"priority must be one of {sorted(allowed_prior)} at {problem_name}/{type_name}")

                levels = t_cfg.get('levels', {})
                if not isinstance(levels, dict):
                    raise ValueError(f"levels must be a mapping at {problem_name}/{type_name}")
                for k, v in levels.items():
                    if not isinstance(k, str) or not isinstance(v, (int, float)):
                        raise ValueError(f"levels entries must be str->number at {problem_name}/{type_name}")

                def _req_list_of_str(field: str) -> List[str]:
                    val = t_cfg.get(field, [])
                    if not isinstance(val, list) or any(not isinstance(x, str) for x in val):
                        raise ValueError(f"{field} must be a list of strings at {problem_name}/{type_name}")
                    return val

                pre_scripts = _req_list_of_str('pre_script')
                post_scripts = _req_list_of_str('post_script')
                user_cmp = _req_list_of_str('user_compare_script')

                # References validation
                refs_cfg = t_cfg.get('reference', [])
                if not isinstance(refs_cfg, list):
                    raise ValueError(f"reference must be a list at {problem_name}/{type_name}")
                refs: List[TestReference] = []
                for r in refs_cfg:
                    if set(r.keys()) != {'name', 'loc', 'file_type'}:
                        raise ValueError(
                            f"reference entries must contain only 'name', 'loc', 'file_type' at {problem_name}/{type_name}")
                    if r['file_type'] not in allowed_ftypes:
                        raise ValueError(
                            f"file_type must be one of {sorted(allowed_ftypes)} at {problem_name}/{type_name}")
                    refs.append(TestReference(name=r['name'], loc=r['loc'], file_type=r['file_type']))

                # Cases validation
                cases_cfg = t_cfg.get('cases', [])
                if not isinstance(cases_cfg, list) or len(cases_cfg) == 0:
                    raise ValueError(f"cases must be a non-empty list at {problem_name}/{type_name}")

                t_type = TestType(
                    name=type_name,
                    priority=priority,
                    levels=levels,
                    pre_scripts=pre_scripts,
                    post_scripts=post_scripts,
                    user_compare_scripts=user_cmp,
                )

                for case_idx, case_cfg in enumerate(cases_cfg):
                    if not isinstance(case_cfg, dict):
                        raise ValueError(f"each case must be a mapping at {problem_name}/{type_name}")
                    if set(case_cfg.keys()) != {"Makefile", "Input__Parameter", "Input__TestProb"}:
                        raise ValueError(
                            f"case configuration must only contain Makefile, Input__Parameter, and Input__TestProb at {problem_name}/{type_name}/case_{case_idx:02d}")
                    mf = case_cfg.get('Makefile', {})
                    ip = case_cfg.get('Input__Parameter', {})
                    it = case_cfg.get('Input__TestProb', {})
                    if not isinstance(mf, dict) or not isinstance(ip, dict) or not isinstance(it, dict):
                        raise ValueError(
                            f"Makefile/Input__* must be mappings at {problem_name}/{type_name}/case_{case_idx:02d}")

                    tc = TestCase(
                        problem_name=problem_name,
                        type_name=type_name,
                        case_index=case_idx,
                        makefile_cfg=mf,
                        input_parameter=ip,
                        input_testprob=it,
                        pre_scripts=pre_scripts.copy(),
                        post_scripts=post_scripts.copy(),
                        user_compare_scripts=user_cmp.copy(),
                        references=refs.copy(),
                        levels=levels.copy(),
                    )
                    t_type.cases.append(tc)

                problem.types.append(t_type)
            problems_model.append(problem)

        self.problems_model = problems_model

    def get_test_cases(
        self,
        name_indices: Optional[List[int]] = None,
        type_indices: Optional[List[int]] = None,
        min_priority: Optional[str] = None,
    ) -> List[TestCase]:
        """Return a flat list of TestCase filtered by problem/type indices and minimum priority."""
        # models are available after __init__

        name_index = self.problems
        type_order = self.type_order

        # Defaults from rtvars
        if name_indices is None:
            name_indices = self.rtvars.name if len(self.rtvars.name) > 0 else list(range(len(name_index)))
        if type_indices is None:
            type_indices = self.rtvars.type if len(self.rtvars.type) > 0 else list(range(len(type_order)))
        if min_priority is None:
            min_priority = self.rtvars.priority

        # Validate indices
        for idx_t in type_indices:
            if idx_t < 0 or idx_t >= len(type_order):
                raise IndexError(f"Unrecognize index of the test type: {idx_t}")
        for idx_n in name_indices:
            if idx_n < 0 or idx_n >= len(name_index):
                raise IndexError(f"Unrecognize index of the test problem: {idx_n}")

        out: List[TestCase] = []
        min_prior_val = PRIOR.get(min_priority, 1)

        # Helper to find problem model by name
        pmap: Dict[str, TestProblem] = {p.name: p for p in self.problems_model}

        for idx_t in type_indices:
            type_name = type_order[idx_t]
            for idx_n in name_indices:
                problem_name = name_index[idx_n]
                p = pmap.get(problem_name)
                if p is None:
                    continue
                # Find matching type in this problem
                t = next((tt for tt in p.types if tt.name == type_name), None)
                if t is None:
                    continue
                if PRIOR.get(t.priority, 1) < min_prior_val:
                    continue
                out.extend(t.cases)

        # Maintain a convenience attribute for callers still using property
        self.test_cases = out
        return out
