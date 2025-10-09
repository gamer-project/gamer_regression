import logging
import os
import subprocess
from typing import Dict, List
from script.argparse import get_runtime_settings
from script.comparator import TestComparator, CompareToolBuilder
from script.logging_center import log_init, set_log_context, clear_log_context, LoggingManager
from script.models import Result, TestCase
from script.run_gamer import TestRunner
from script.runtime_vars import RuntimeVariables
from script.summary import generate_summaries
from script.test_explorer import TestExplorer
from script.utilities import STATUS, time_step


"""
TODO:
1. rename variables
2. remove the unused variables
3. clean every thing about the path

Documents:
1. the file structure is assumed
2. how to add a test
3. how to modify
4. the logic of regression test
"""


####################################################################################################
# Functions
####################################################################################################
def get_git_info():
    """
    Get the current gamer hash.

    Returns
    -------

    gamer_commit      : str
       gamer commit hash
    """
    try:
        gamer_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except:
        gamer_commit = "UNKNOWN"

    return gamer_commit


def main(rtvars: RuntimeVariables, test_cases: List[TestCase]) -> Dict[str, Result]:
    """
    Main regression test.

    Parameters
    ----------
    rtvars : RuntimeVariables
        Runtime variables containing configuration.
    test_cases : List[TestCase]
        List of test cases to execute.

    Returns
    -------
    Dict[str, Result]
        Dictionary mapping test_id to Result objects.
    """

    results: Dict[str, Result] = {}
    tool_builder = CompareToolBuilder(rtvars)
    comparator = TestComparator(rtvars, tool_builder)

    for tc in test_cases:
        # Prepare per-case run dir
        logger = logging.getLogger('runner')
        run_dir = tc.run_dir(rtvars)
        if os.path.isdir(run_dir):
            subprocess.check_call(['rm', '-rf', run_dir])
            logger.warning(f"Run directory {run_dir} exists. Removed.")
        os.makedirs(os.path.dirname(run_dir), exist_ok=True)

        # Run case
        runner = TestRunner(rtvars, tc, rtvars.gamer_path)
        timing = {}  # Collect timing for all steps

        try:
            set_log_context(test_id=tc.test_id, phase='start')
            logger.info('Start running case')

            set_log_context(phase='compile')
            os.chdir(os.path.join(rtvars.gamer_path, 'src'))
            with time_step('compile_gamer', timing, logger):
                if runner.compile_gamer() != STATUS.SUCCESS:
                    results[tc.test_id] = Result(status=runner.status, reason=runner.reason, timing=timing)
                    continue

            set_log_context(phase='prepare')
            with time_step('copy_case', timing, logger):
                if runner.copy_case() != STATUS.SUCCESS:
                    results[tc.test_id] = Result(status=runner.status, reason=runner.reason, timing=timing)
                    continue

            set_log_context(phase='set_input')
            os.chdir(runner.case_dir)
            with time_step('set_input', timing, logger):
                if runner.set_input() != STATUS.SUCCESS:
                    results[tc.test_id] = Result(status=runner.status, reason=runner.reason, timing=timing)
                    continue

            set_log_context(phase='pre_script')
            with time_step('pre_script', timing, logger):
                if runner.execute_scripts('pre_script') != STATUS.SUCCESS:
                    results[tc.test_id] = Result(status=runner.status, reason=runner.reason, timing=timing)
                    continue

            set_log_context(phase='run')
            with time_step('run_gamer', timing, logger):
                if runner.run_gamer() != STATUS.SUCCESS:
                    results[tc.test_id] = Result(status=runner.status, reason=runner.reason, timing=timing)
                    continue

            set_log_context(phase='post_script')
            with time_step('post_script', timing, logger):
                if runner.execute_scripts('post_script') != STATUS.SUCCESS:
                    results[tc.test_id] = Result(status=runner.status, reason=runner.reason, timing=timing)
                    continue

            # Compare
            set_log_context(phase='compare')
            status, reason = comparator.compare(tc)

            # Merge comparator's detailed timing into main timing dict
            for key, value in comparator.timing.items():
                timing[f'compare_{key}'] = value

            results[tc.test_id] = Result(status=status, reason=reason, timing=timing)
            logger.info('Case done')
        finally:
            clear_log_context()

    return results


def write_args_to_log(rtvars: RuntimeVariables):
    logger = logging.getLogger('main')
    logger.info("Record all arguments have been set.")

    # Log fields from rtvars dataclass
    for field, value in vars(rtvars).items():
        if isinstance(value, str):
            logger.info("%-20s : %s" % (field, value))
        elif isinstance(value, int):
            logger.info("%-20s : %d" % (field, value))
        elif isinstance(value, float):
            logger.info("%-20s : %f" % (field, value))
        elif isinstance(value, bool):
            logger.info("%-20s : %r" % (field, value))
        else:
            logger.info("%-20s : %s" % (field, value))
    return


####################################################################################################
# Main execution
####################################################################################################
if __name__ == '__main__':
    rtvars = get_runtime_settings()

    test_explorer = TestExplorer(rtvars)

    GAMER_EXPECT_COMMIT = "13409ab33b12d84780076b6a9beb07317ca145f1"
    GAMER_CURRENT_COMMIT = get_git_info()

    # Initialize regression test
    # Use new flat list of cases produced by TestExplorer
    test_cases = test_explorer.get_test_cases(min_priority=rtvars.priority, tags=rtvars.tags)

    # Initialize logger
    log_init(rtvars.output)

    logger = logging.getLogger('main')

    logger.info('Recording the commit version.')
    logger.info('GAMER      version   : %-s' % (GAMER_CURRENT_COMMIT))

    if GAMER_CURRENT_COMMIT != GAMER_EXPECT_COMMIT:
        logger.warning('Regression test may not fully support this GAMER version!')

    write_args_to_log(rtvars)

    keys = sorted(tc.test_id for tc in test_cases)
    logger.info('Test to be run       : %-s' % (" ".join(keys)))

    # Regression test
    try:
        logger.info('Regression test start.')
        result = main(rtvars, test_cases)
        logger.info('Regression test done.')
    except Exception:
        logger.exception('Unexpected Error')
        raise

    generate_summaries(rtvars, result)

    # Ensure all queued logs are written before program exit
    LoggingManager.shutdown()
