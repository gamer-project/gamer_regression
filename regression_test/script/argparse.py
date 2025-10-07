import argparse
import os
from .runtime_vars import RuntimeVariables

thread_nums = os.cpu_count()
THREAD_PER_CORE = 2
CORE_PER_RANK = 8
core_nums = thread_nums // THREAD_PER_CORE
RANK_NUMS = core_nums // CORE_PER_RANK


def get_runtime_settings() -> RuntimeVariables:
    """
    Handle the input arguments and create a RuntimeVariables instance
    to store the settings.
    """
    parser = argparse.ArgumentParser(
        description="Regression test of GAMER (commit ?).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-e", "--error-level",
                        help="level of error allowed",
                        type=int, choices=[0, 1, 2],
                        default=0
                        )
    parser.add_argument("-p", "--priority",
                        help="minimum priority of test cases to run; could be high, medium, low, or a non-negative integer",
                        default="high"
                        )
    parser.add_argument("-t", "--tags",
                        nargs="+",
                        help="select tests that contain ALL tags"
                        )
    parser.add_argument("-o", "--output",
                        help="name of the log file; .log will be appended if not provided",
                        type=str,
                        default="test.log"
                        )
    parser.add_argument("-u", "--update-ref",
                        help="use new result to update reference data",
                        action="store_true"
                        )

    parser.add_argument("-m", "--machine",
                        help="name of the machine configuration in gamer/configs",
                        default="eureka_intel")
    parser.add_argument("-r", "--reference-loc",
                        help="reference data source; either 'cloud', 'local', or a prefixed spec like 'local:/abs/path'",
                        dest="reference_loc",
                        type=str,
                        default="local")
    parser.add_argument("--reports",
                        nargs="+",
                        help="list of summary report generators to use",
                        default=["WSXCYC", "TIMING"]
                        )

    # MPI arguments
    parser.add_argument("--mpi-rank", metavar="N_RANK",
                        help="number of mpi ranks",
                        type=int,
                        default=RANK_NUMS
                        )
    parser.add_argument("--mpi-core-per-rank", metavar="N_CORE",
                        help="core used per rank",
                        type=int,
                        default=CORE_PER_RANK
                        )

    args = parser.parse_args()

    return RuntimeVariables(**vars(args))
