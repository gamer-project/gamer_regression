from dataclasses import dataclass
from typing import ClassVar, List, Optional
import os
import sys
from .utilities import priority2int


# TODO: The name is confusing. Maybe rename to RuntimeConfig or RuntimeSettings?
@dataclass(frozen=True)
class RuntimeVariables:
    num_threads: ClassVar[int]
    gamer_path: ClassVar[str]
    py_exe: ClassVar[str]
    error_level: int
    priority: int
    output: str
    update_ref: bool
    machine: str
    mpi_rank: int
    mpi_core_per_rank: int
    tags: Optional[List[str]]
    reference_loc: str
    reports: List[str]

    def __post_init__(self):
        object.__setattr__(self, "num_threads", os.cpu_count())
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), *(os.pardir, ) * 2))
        object.__setattr__(self, "gamer_path", repo_root)
        object.__setattr__(self, "py_exe", sys.executable)

        object.__setattr__(self, "priority", priority2int(self.priority))
        if self.output and not self.output.endswith(".log"):
            object.__setattr__(self, "output", self.output + ".log")
