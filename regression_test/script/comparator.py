import copy
import hashlib
import json
import logging
import numpy as np
import os
import re
import time
from os.path import isfile
from typing import Dict, Tuple
from .hdf5_file_config import hdf_info_read
from .models import TestCase
from .reference import MissingReferenceError, ReferenceError, get_provider
from .runtime_vars import RuntimeVariables
from .utilities import STATUS, time_step
from .process_runner import run_process


class CompareToolBuilder:
    def __init__(self, rtvars: RuntimeVariables):
        self.rtvars = rtvars

    def get_tool(self, case: TestCase) -> Tuple[int, str, str]:
        """Returns (STATUS, reason, tool_path). Builds if needed."""
        logger = logging.getLogger('compare.build')
        base = os.path.join(self.rtvars.gamer_path, 'tool', 'analysis', 'gamer_compare_data')
        paths = self._machine_paths(self.rtvars.gamer_path, self.rtvars.machine)
        sig = self._config_hash(case.makefile_cfg, paths)
        tools_root = os.path.join(self.rtvars.gamer_path, 'regression_test', 'run', 'tools', sig)
        exe = os.path.join(tools_root, 'GAMER_CompareData')
        if os.path.isfile(exe):
            return STATUS.SUCCESS, "", exe

        os.makedirs(tools_root, exist_ok=True)
        makefile_path = os.path.join(base, 'Makefile')
        makefile_origin = os.path.join(base, 'Makefile.origin')
        # Build with streaming logs and tee to make.log
        try:
            os.rename(makefile_path, makefile_origin)
            with open(makefile_origin) as f:
                content = f.read()
            for k, v in paths.items():
                content = content.replace(k + " :=", k + f" := {v}\n#")

            model = case.makefile_cfg.get('model', 'HYDRO')
            if model == 'HYDRO':
                content = content.replace("SIMU_OPTION += -DMODEL=HYDRO", "SIMU_OPTION += -DMODEL=HYDRO")
            elif model == 'ELBDM':
                content = content.replace("SIMU_OPTION += -DMODEL=HYDRO", "SIMU_OPTION += -DMODEL=ELBDM")
            else:
                raise ValueError(f"Unknown model {model} in case {case.test_id}")

            if case.makefile_cfg.get('double', False):
                content = content.replace("#SIMU_OPTION += -DFLOAT8", "SIMU_OPTION += -DFLOAT8")
            if case.makefile_cfg.get('debug', False):
                content = content.replace("#SIMU_OPTION += -DGAMER_DEBUG", "SIMU_OPTION += -DGAMER_DEBUG")
            if case.makefile_cfg.get('hdf5', False):
                content = content.replace("#SIMU_OPTION += -DSUPPORT_HDF5", "SIMU_OPTION += -DSUPPORT_HDF5")

            with open(makefile_path, 'w') as f:
                f.write(content)

            os.chdir(base)
            run_process(['make', 'clean'])
            run_process('make', shell=True, tee_stdout='make.log', merge_streams=True)
            if not os.path.isfile(os.path.join(base, 'GAMER_CompareData')):
                return STATUS.COMPILE_ERR, 'Compare tool missing after build', ''

            os.rename(os.path.join(base, 'GAMER_CompareData'), exe)
            try:
                os.remove(os.path.join(base, 'make.log'))
            except Exception:
                pass
            return STATUS.SUCCESS, "", exe
        except Exception as e:
            return STATUS.COMPILE_ERR, f"Error while compiling the compare tool: {e}", ''
        finally:
            try:
                if os.path.exists(makefile_path):
                    os.remove(makefile_path)
                if os.path.exists(makefile_origin):
                    os.rename(makefile_origin, makefile_path)
            except Exception:
                pass

    def _machine_paths(self, gamer_abs_path: str, machine: str) -> Dict[str, str]:
        config_file = f"{gamer_abs_path}/configs/{machine}.config"
        paths: Dict[str, str] = {}
        with open(config_file, 'r') as f:
            for line in f:
                if 'PATH' not in line:
                    continue
                temp = list(filter(None, re.split(" |:=|\n", line)))
                if not temp:
                    continue
                key = temp[0]
                val = temp[1] if len(temp) > 1 else ''
                paths[key] = val
        return paths

    def _config_hash(self, make_cfg: Dict[str, object], machine_paths: Dict[str, str]) -> str:
        data = {"Makefile": make_cfg, "paths": machine_paths}
        s = json.dumps(data, sort_keys=True)
        return hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]


class TestComparator:
    def __init__(self, rtvars: RuntimeVariables, tool_builder: CompareToolBuilder):
        self.rtvars = rtvars
        self.gamer_abs_path = rtvars.gamer_path
        self.tool_builder = tool_builder
        self.timing = {}  # Store timing for each comparison step

    def compare(self, case: TestCase) -> Tuple[int, str]:
        logger = logging.getLogger('compare')
        case_dir = case.run_dir(self.rtvars)

        # Clear timing from previous run
        self.timing.clear()

        # 1) Get references
        ref_missing = False
        with time_step('fetch_references', self.timing, logger):
            try:
                ref_root = self._fetch_references(case)
            except MissingReferenceError as exc:
                if self.rtvars.update_ref:
                    logger.info(f"No reference found for {case.test_id}. Will create new reference.")
                    ref_missing = True
                    ref_root = None
                else:
                    return exc.status, str(exc)
            except ReferenceError as exc:
                return exc.status, str(exc)
            except Exception as exc:
                return STATUS.FAIL, f"Unexpected reference error: {exc}"

        # 2) Build/ensure compare tool
        with time_step('build_compare_tool', self.timing, logger):
            tool_status, tool_reason, tool_path = self._build_compare_tool(case)

        # 3) Run comparisons (skip if reference is missing and update_ref is set)
        with time_step('run_comparisons', self.timing, logger):
            if ref_missing:
                # TODO: should report by another status to reduce confusion?
                logger.info(f"Skipping comparison for {case.test_id} (no reference, update mode)")
                status, reason = STATUS.SUCCESS, ""
            else:
                status, reason = self._run_comparisons(case, ref_root, tool_status, tool_reason, tool_path)
                if status != STATUS.SUCCESS and not self.rtvars.update_ref:
                    return status, reason

        # 4) Push references if update_ref is enabled
        if self.rtvars.update_ref:
            with time_step('push_references', self.timing, logger):
                try:
                    from .reference import get_provider
                    provider = get_provider(self.rtvars)
                    provider.push(case, case_dir)
                    logger.info(f"Reference updated for {case.test_id}")
                except Exception as exc:
                    logger.error(f"Failed to push reference: {exc}")
                    return STATUS.FAIL, f"Reference update failed: {exc}"

        return STATUS.SUCCESS, ""

    # ---- internals: step 1 - reference staging ----
    def _fetch_references(self, case: TestCase) -> str:
        provider = get_provider(self.rtvars)
        return provider.fetch(case)

    # ---- internals: step 2 - tool ensure/build ----
    def _build_compare_tool(self, case: TestCase) -> Tuple[int, str, str]:
        return self.tool_builder.get_tool(case)

    # ---- internals: step 3 - comparisons ----
    def _run_comparisons(self, case: TestCase, ref_root: str,
                         tool_status: int, tool_reason: str, tool_path: str) -> Tuple[int, str]:
        err_level = f"level{self.rtvars.error_level}"
        case_dir = case.run_dir(self.rtvars)
        for ref in case.references:
            fname = os.path.basename(ref.name)
            cur_path = os.path.join(case_dir, fname)
            ref_path = os.path.join(ref_root, fname)
            if ref.file_type == 'TEXT':
                failed = self._compare_text(cur_path, ref_path, case.levels[err_level])
            elif ref.file_type == 'HDF5':
                if tool_status != STATUS.SUCCESS:
                    return STATUS.COMPARISON, tool_reason or 'Compare tool unavailable'
                failed = self._compare_hdf5(tool_path, cur_path, ref_path, case.levels[err_level])
            elif ref.file_type == 'NOTE':
                failed = self._compare_note(cur_path, ref_path)
            else:
                return STATUS.FAIL, f"Unknown file_type {ref.file_type}"
            if failed:
                return STATUS.COMPARISON, 'Fail data comparison.'

        # user compare scripts
        for script in case.user_compare_scripts:
            try:
                if not os.path.isfile(script):
                    continue
                run_process(['sh', script, case_dir])
            except Exception:
                return STATUS.EXTERNAL, f"Error while executing {script}"
        return STATUS.SUCCESS, ""

    # ---- comparison helpers ----
    def _compare_text(self, result_file, expect_file, err_allowed) -> bool:
        # TODO: support the user compare range(data)
        logger = logging.getLogger('compare.text')
        logger.info(f"Comparing TEXT: {result_file} <--> {expect_file}")
        if not os.path.isfile(result_file):
            logger.error(f"Result file is missing: {result_file}")
            return True
        if not os.path.isfile(expect_file):
            logger.error(f"Reference file is missing: {expect_file}")
            return True
        try:
            a = np.loadtxt(result_file)
            b = np.loadtxt(expect_file)
        except Exception as e:
            logger.error(f"Error reading TEXT files: {e}")
            return True
        if a.shape != b.shape:
            logger.error('Data compare: data shapes are different.')
            return True
        err = np.max(np.abs(a - b))
        if err > err_allowed:
            logger.debug('Error is greater than expect. Expected: %.4e. Test: %.4e.' % (err_allowed, err))
            return True
        logger.info("Comparing TEXT done.")
        return False

    def _compare_hdf5(self, tool_path, result_file, expect_file, err_allowed) -> bool:
        logger = logging.getLogger('compare.hdf5')
        logger.info(f"Comparing HDF5: {result_file} <--> {expect_file}")
        compare_program = tool_path
        compare_result = os.path.join(os.path.dirname(tool_path), 'compare_result')
        result_info = hdf_info_read(result_file)
        expect_info = hdf_info_read(expect_file)
        cmd = [compare_program, '-i', result_file, '-j', expect_file,
               '-o', compare_result, '-e', str(err_allowed), '-c', '-m']

        # Run compare tool: tee stdout to compare.log (overwrite), stream both streams to logger
        compare_log_path = os.path.join(os.path.dirname(tool_path), 'compare.log')
        if os.path.exists(compare_log_path):
            os.remove(compare_log_path)
        returncode = run_process(cmd, tee_stdout=compare_log_path, check=False)
        if returncode != 0:
            return True  # Running the tool failed (non-zero exit)

        fail_compare = False
        try:
            with open(compare_result, 'r') as f:
                for line in f:
                    if line and line[0] not in ['#', '\n']:
                        fail_compare = True
                        break
        except Exception:
            fail_compare = True
        if fail_compare:
            logger.error('Result data is not identical to expect data')
            logger.error('Error is greater than expected.')
            str_len = str(max(len(expect_file), len(result_file), 50))
            str_format = "%-"+str_len+"s %-"+str_len+"s"
            logger.error('Type      : '+str_format % ("Expect",              "Result"))
            logger.error('File name : '+str_format % (expect_file,           result_file))
            logger.error('Git Branch: '+str_format % (expect_info.gitBranch, result_info.gitBranch))
            logger.error('Git Commit: '+str_format % (expect_info.gitCommit, result_info.gitCommit))
            logger.error('Unique ID : '+str_format % (expect_info.DataID,    result_info.DataID))
        logger.info("Comparing HDF5 done.")
        return fail_compare

    @staticmethod
    def _store_note_para(file_name):
        with open(file_name, "r") as f:
            data = f.readlines()
        paras = {}
        in_section = False
        cur_sec = ""
        section_pattern = "*****"
        skip_sec = [
            "Flag Criterion (# of Particles per Patch)",
            "Flag Criterion (Lohner Error Estimator)",
            "Cell Size and Scale (scale = number of cells at the finest level)",
            "Compilation Time",
            "Current Time",
        ]
        end_sec = ["OpenMP Diagnosis", "Device Diagnosis"]
        for i in range(len(data)):
            if data[i] == "\n":
                continue
            if section_pattern in data[i]:
                in_section = not in_section
                continue
            if not in_section:
                sec = data[i].rstrip()
                cur_sec = sec
                if cur_sec in end_sec:
                    break
                paras[cur_sec] = {}
                continue
            if cur_sec in skip_sec:
                continue
            para = data[i].rstrip().split()
            key = " ".join(para[0:-1])
            paras[cur_sec][key] = para[-1]
        return paras

    @staticmethod
    def _diff_note_para(para_1: dict, para_2: dict) -> dict:
        """Legacy-compatible parameter diff used for detailed logging.

        Returns a dict {"1": {key: val1_or_EMPTY}, "2": {key: val2_or_EMPTY}} aggregating all diffs.
        """
        p1 = copy.deepcopy(para_1)
        p2 = copy.deepcopy(para_2)
        diff = {"1": {}, "2": {}}
        for sec in list(para_1.keys()):
            if sec not in para_2:
                for k in para_1[sec]:
                    diff["1"][k] = para_1[sec][k]
                    diff["2"][k] = "EMPTY"
                continue
            for k in list(para_1[sec].keys()):
                if k not in para_2[sec]:
                    diff["1"][k] = para_1[sec][k]
                    diff["2"][k] = "EMPTY"
                    p1[sec].pop(k, None)
                    continue
                if para_1[sec][k] != para_2[sec][k]:
                    diff["1"][k] = para_1[sec][k]
                    diff["2"][k] = para_2[sec][k]
                p1[sec].pop(k, None)
                p2[sec].pop(k, None)
            # remaining only-in-para2
            for k in list(p2.get(sec, {}).keys()):
                diff["1"][k] = "EMPTY"
                diff["2"][k] = para_2[sec][k]
            p1.pop(sec, None)
            p2.pop(sec, None)
        for sec in list(para_2.keys()):
            if sec in para_1:
                continue
            for k in para_2[sec]:
                diff["1"][k] = "EMPTY"
                diff["2"][k] = para_2[sec][k]
            p2.pop(sec, None)
        return diff

    def _compare_note(self, result_note, expect_note) -> bool:
        logger = logging.getLogger('compare.note')
        fail_compare = False
        # TODO: Should this allways return passing?
        if not isfile(result_note) or not isfile(expect_note):
            return fail_compare
        logger.info(f"Comparing Record__Note: {result_note} <-> {expect_note}")
        para_result = self._store_note_para(result_note)
        para_expect = self._store_note_para(expect_note)
        diff = self._diff_note_para(para_result, para_expect)
        logger.debug("%-30s | %40s | %40s |" % ("Parameter name", "result parameter", "expect parameter"))
        for key in diff["1"]:
            logger.debug("%-30s | %40s | %40s |" % (key, diff["1"][key], diff["2"][key]))
        logger.info("Comparison of Record__Note done.")
        return fail_compare
