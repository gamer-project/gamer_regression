from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RuntimeVariables:
    num_threads: int
    gamer_path: str
    py_exe: str
    error_level: int
    priority: int
    output: str
    no_upload: bool
    machine: str
    mpi_rank: int
    mpi_core_per_rank: int
    tags: Optional[List[str]]
