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


SUMMARY_GENERATOR_REGISTRY: Dict[str, Type[SummaryGenerator]] = {
    'WSXCYC': WSXCYCSummaryGenerator,
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
