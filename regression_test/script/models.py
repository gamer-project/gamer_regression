from dataclasses import dataclass, field
from typing import Any, Dict, List


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
    # Path to run/<test_id> directory (set by orchestrator)
    run_dir: str = ""
    # Properties for new YAML config
    path: str = ""
    source: str = ""
    priority: int | str = 0
    tags: List[str] = field(default_factory=list)

    @property
    def test_group(self) -> str:
        # Deprecated: legacy grouped identity (<TestName>_<Type>)
        # Still be used in GirderReferenceProvider
        return f"{self.problem_name}_{self.type_name}"

    @property
    def case_name(self) -> str:
        return f"case_{self.case_index:02d}"

    @property
    def test_id(self) -> str:
        """Flattened unique per-case identity.

        Format: <TestName>_<Type>_c<case_index:02d>
        """
        return f"{self.problem_name}_{self.type_name}_c{self.case_index:02d}"

    @staticmethod
    def from_node_attributes(attrs: dict[str, Any]) -> 'TestCase':
        """Construct a TestCase from a _DataNode instance."""

        def get_attr(attrs, key: str, default=None, expect_type=None):
            if attrs is None:
                return default
            v = attrs.get(key)
            if v is None:
                return default
            if expect_type and not isinstance(v, expect_type):
                raise ValueError(f"Expected {key} to be of type {expect_type}, got {type(v)}")
            return v

        fields = {}  # TestCase fields

        fields['makefile_cfg'] = get_attr(attrs, 'options', {})

        inputs = get_attr(attrs, 'inputs', {}, dict)
        fields['input_parameter'] = get_attr(inputs, 'Input__Parameter', {}, dict)
        fields['input_testprob'] = get_attr(inputs, 'Input__TestProb', {}, dict)

        fields['priority'] = get_attr(attrs, 'priority', 0, (int, str))
        fields['levels'] = get_attr(attrs, 'levels', {}, dict)

        references: List[TestReference] = []
        for ref in get_attr(attrs, 'references', [], list):
            references.append(TestReference(
                name=ref['name'],
                loc=ref['loc'],
                file_type=ref['file_type']
            ))
        fields['references'] = references

        # Optional attributes
        fields['pre_scripts'] = get_attr(attrs, 'pre_scripts', [], list)
        fields['post_scripts'] = get_attr(attrs, 'post_scripts', [], list)
        fields['user_compare_scripts'] = get_attr(attrs, 'user_compare_scripts', [], list)

        fields['path'] = get_attr(attrs, 'path', "", str)
        fields['source'] = get_attr(attrs, 'source', "", str)
        fields['tags'] = get_attr(attrs, 'tags', [], list)

        # To be deprecated:
        fields['problem_name'] = "new_structure"
        fields['type_name'] = fields.get('path', '').replace('/', '_').replace('\\', '_')
        fields['case_index'] = 0

        return TestCase(**fields)


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
