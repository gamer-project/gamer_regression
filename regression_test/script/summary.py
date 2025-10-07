import os
import logging
from typing import Dict, Type
from .models import Result
from .runtime_vars import RuntimeVariables
from .utilities import STATUS


class SummaryGenerator:
    """Base class for generating test result summaries."""

    def __init__(self, rtvars: RuntimeVariables):
        """Initialize the summary generator with runtime variables.

        Parameters
        ----------
        rtvars : RuntimeVariables
            Runtime variables containing configuration information.
        """
        self.rtvars = rtvars

    def generate(self, results: Dict[str, Result]) -> None:
        """Generate and output a summary of test results.

        Parameters
        ----------
        results : Dict[str, Result]
            Dictionary mapping test_id to Result objects.
        """
        raise NotImplementedError("Subclasses must implement generate()")


class WSXCYCSummaryGenerator(SummaryGenerator):
    """The original `output_summary` function adapted into a class.
       Original author: xuanweishan, ChunYen-Chen
    """

    def generate(self, results: Dict[str, Result]) -> None:
        logger = logging.getLogger('summary')

        TEXT_RED = "\033[91m"
        TEXT_GREEN = "\033[92m"
        TEXT_RESET = "\033[0m"
        SEP_LEN = 50
        OUT_FORMAT = "%-30s: %-15s %s"

        separator = "=" * SEP_LEN
        logger.info(separator)
        logger.info("Short summary: (Fail will be colored as red, passed will be colored as green.)")
        logger.info(separator)
        logger.info(OUT_FORMAT % ("Test name", "Error code", "Reason"))

        for test_id, result in results.items():
            color = TEXT_GREEN if result.status == STATUS.SUCCESS else TEXT_RED
            line = OUT_FORMAT % (test_id, STATUS.CODE_TABLE[result.status], result.reason)
            logger.info(color + line + TEXT_RESET)

        logger.info(separator)
        logger.info("Please check <%s> for the detailed message." % self.rtvars.output)


class TimingSummaryGenerator(SummaryGenerator):
    """Generate a timing summary file showing execution times for each test case step."""

    def generate(self, results: Dict[str, Result]) -> None:
        # Generate output filename: remove .log extension and add _time.log
        # Ensure we use absolute path based on gamer_path
        base_name = self.rtvars.output
        if not os.path.isabs(base_name):
            base_name = os.path.join(self.rtvars.gamer_path, 'regression_test', base_name)
        if base_name.endswith('.log'):
            base_name = base_name[:-4]
        timing_file = base_name + '_timing.log'

        logger = logging.getLogger('summary.timing')
        logger.info(f"Generating timing summary to: {timing_file}")

        with open(timing_file, 'w') as f:
            # Write header
            f.write("=" * 100 + "\n")
            f.write("Timing Summary Report\n")
            f.write("=" * 100 + "\n\n")

            # Collect all unique step names across all tests
            all_steps = set()
            for result in results.values():
                all_steps.update(result.timing.keys())
            all_steps = sorted(all_steps)

            # Write timing for each test case
            for test_id, result in results.items():
                f.write(f"\nTest: {test_id}\n")
                f.write(f"Status: {STATUS.CODE_TABLE[result.status]}")
                if result.reason:
                    f.write(f" ({result.reason})")
                f.write("\n")
                f.write("-" * 100 + "\n")

                if not result.timing:
                    f.write("  No timing data available\n")
                else:
                    # Calculate total time
                    total_time = sum(result.timing.values())

                    # Write each step's timing
                    f.write(f"  {'Step':<40} {'Time (s)':>12} {'Percentage':>12}\n")
                    f.write(f"  {'-'*40} {'-'*12} {'-'*12}\n")

                    for step in all_steps:
                        if step in result.timing:
                            time_val = result.timing[step]
                            percentage = (time_val / total_time * 100) if total_time > 0 else 0
                            f.write(f"  {step:<40} {time_val:>12.3f} {percentage:>11.1f}%\n")

                    f.write(f"  {'-'*40} {'-'*12} {'-'*12}\n")
                    f.write(f"  {'TOTAL':<40} {total_time:>12.3f} {100.0:>11.1f}%\n")

                f.write("\n")

            # Write summary statistics
            f.write("\n" + "=" * 100 + "\n")
            f.write("Summary Statistics\n")
            f.write("=" * 100 + "\n\n")

            # Calculate average timing for each step
            step_totals = {}
            step_counts = {}
            for result in results.values():
                for step, time_val in result.timing.items():
                    step_totals[step] = step_totals.get(step, 0) + time_val
                    step_counts[step] = step_counts.get(step, 0) + 1

            if step_totals:
                f.write(f"  {'Step':<40} {'Avg Time (s)':>15} {'Total Time (s)':>15} {'Count':>10}\n")
                f.write(f"  {'-'*40} {'-'*15} {'-'*15} {'-'*10}\n")

                for step in sorted(step_totals.keys()):
                    avg_time = step_totals[step] / step_counts[step]
                    total_time = step_totals[step]
                    count = step_counts[step]
                    f.write(f"  {step:<40} {avg_time:>15.3f} {total_time:>15.3f} {count:>10}\n")

                grand_total = sum(step_totals.values())
                f.write(f"  {'-'*40} {'-'*15} {'-'*15} {'-'*10}\n")
                f.write(f"  {'GRAND TOTAL':<40} {' ':>15} {grand_total:>15.3f} {' ':>10}\n")

            f.write("\n" + "=" * 100 + "\n")

        logger.info(f"Timing summary written to: {timing_file}")


SUMMARY_GENERATOR_REGISTRY: Dict[str, Type[SummaryGenerator]] = {
    'WSXCYC': WSXCYCSummaryGenerator,
    'TIMING': TimingSummaryGenerator,
}


def get_summary_generator(name: str) -> Type[SummaryGenerator]:
    """Get a SummaryGenerator class by name."""
    if name not in SUMMARY_GENERATOR_REGISTRY:
        available = ", ".join(SUMMARY_GENERATOR_REGISTRY.keys())
        raise ValueError(f"Unknown summary generator: {name}. Available: {available}")
    return SUMMARY_GENERATOR_REGISTRY[name]


def generate_summaries(rtvars: RuntimeVariables, results: Dict[str, Result]) -> None:
    """Generate summaries using all specified report generators.

    Parameters
    ----------
    rtvars : RuntimeVariables
        Runtime variables containing the list of report generators to use.
    results : Dict[str, Result]
        Dictionary mapping test_id to Result objects.
    """
    logger = logging.getLogger('summary')

    if not rtvars.reports:
        logger.warning("No summary generators specified in rtvars.reports")
        return

    for generator_name in rtvars.reports:
        try:
            logger.info(f"Generating summary using: {generator_name}")
            TheSummaryGenerator = get_summary_generator(generator_name)
            TheSummaryGenerator(rtvars).generate(results)
        except ValueError as e:
            logger.error(f"Failed to load generator '{generator_name}': {e}")
        except Exception as e:
            logger.exception(f"Error while generating summary with '{generator_name}': {e}")
