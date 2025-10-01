import argparse
import os

PRIOR = {"high": 3, "medium": 2, "low": 1}

thread_nums = os.cpu_count()
THREAD_PER_CORE = 2
CORE_PER_RANK = 8
core_nums = thread_nums // THREAD_PER_CORE
RANK_NUMS = core_nums // CORE_PER_RANK


def argument_handler():
    """
    Get the input arguements.

    Returns
    -------

    args    : class argparse.Namespace
       Storing the input arguments.

    unknown : list of string
       Storing the unknown argument input.

    """
    parser = argparse.ArgumentParser(description="Regression test of GAMER (commit ?).",
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     allow_abbrev=False        # python version must be >= 3.5
                                     )

    parser.add_argument("-e", "--error_level",
                        help="Error allowed in this test. \nDefault: %(default)s",
                        type=str, choices=["level0", "level1", "level2"],
                        default="level0"
                        )
    parser.add_argument("-p", "--priority",
                        help="Priority of the regression test. \nDefault: %(default)s",
                        type=str, choices=[i for i in PRIOR],
                        default="high"
                        )
    parser.add_argument("-o", "--output",
                        help="Set the file name of the test log. The output file will be added a suffix '.log' automatically. \nDefault: %(default)s",
                        type=str,
                        default="test"
                        )
    parser.add_argument("-u", "--no-upload",
                        help="Do not ask if needs to upload new answer to cloud.",
                        action="store_true"
                        )

    parser.add_argument("-m", "--machine",
                        help="Select the machine configuration in ../configs. \nDefault: %(default)s",
                        default="eureka_intel")

    # MPI arguments
    parser.add_argument("--mpi_rank", metavar="N_RANK",
                        help="Number of ranks of mpi. \nDefault: %(default)s",
                        type=int,
                        default=RANK_NUMS
                        )
    parser.add_argument("--mpi_core_per_rank", metavar="N_CORE",
                        help="Core used per rank. \nDefault: %(default)s",
                        type=int,
                        default=CORE_PER_RANK
                        )

    args, unknown = parser.parse_known_args()

    # Print out the unknown arguments
    if unknown != []:
        print("Simulation forced arguments or unknown arguments: ", unknown)

    return args, unknown
