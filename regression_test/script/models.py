from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class TestReference:
    name: str            # relative path under run dir (e.g., case_00/Data_...)
    loc: str             # e.g., "local:/abs/path" or "cloud:case_00/..."
    file_type: str       # HDF5 | TEXT | NOTE


@dataclass
class TestCase:
    problem_name: str                 # <TestName>
    type_name: str                    # <Type>
    case_index: int                   # numeric index, 0-based
    makefile_cfg: Dict[str, object]   # Makefile options
    input_parameter: Dict[str, object]
    input_testprob: Dict[str, object]
    pre_scripts: List[str] = field(default_factory=list)
    post_scripts: List[str] = field(default_factory=list)
    user_compare_scripts: List[str] = field(default_factory=list)
    references: List[TestReference] = field(default_factory=list)
    levels: Dict[str, float] = field(default_factory=dict)

    @property
    def test_key(self) -> str:
        return f"{self.problem_name}_{self.type_name}"

    @property
    def case_name(self) -> str:
        return f"case_{self.case_index:02d}"


@dataclass
class TestType:
    name: str                           # <Type>
    priority: str                       # high | medium | low
    levels: Dict[str, float]
    pre_scripts: List[str] = field(default_factory=list)
    post_scripts: List[str] = field(default_factory=list)
    user_compare_scripts: List[str] = field(default_factory=list)
    cases: List[TestCase] = field(default_factory=list)


@dataclass
class TestProblem:
    name: str                           # <TestName>
    types: List[TestType] = field(default_factory=list)
