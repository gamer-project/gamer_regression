from dataclasses import dataclass


@dataclass
class RuntimeVariables:
    num_threads: int
    gamer_path: str
    py_exe: str
    error_level: str
    priority: str
    output: str
    no_upload: bool
    machine: str
    mpi_rank: int
    mpi_core_per_rank: int
