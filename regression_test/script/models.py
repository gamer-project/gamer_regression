import hashlib
import json
import os
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, ClassVar, Dict, List, Optional
from .runtime_vars import RuntimeVariables
from .utilities import priority2int, STATUS


@dataclass()
class Result:
    """Result of a test case."""
    status: STATUS
    reason: str
    timing: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TestReference:
    name: str            # file name under run dir (e.g., Data_...)
    file_type: str       # HDF5 | TEXT | NOTE


@dataclass(frozen=True)
class TestCase:

    makefile_cfg: Dict[str, object]   # Makefile options
    input_parameter: Dict[str, object]
    input_testprob: Dict[str, object]
    pre_scripts: List[str] = field(default_factory=list)
    post_scripts: List[str] = field(default_factory=list)
    user_compare_scripts: List[str] = field(default_factory=list)
    references: List[TestReference] = field(default_factory=list)
    levels: Dict[str, float] = field(default_factory=dict)
    path: str = ""
    source: str = ""
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    # Optional fields for input from config
    _case_name: Optional[str] = None
    # TODO: a corresponding field case_name set by __post_init__

    # Class variables
    _all_test_ids: ClassVar[set[str]] = set()

    def run_dir(self, rtvars: RuntimeVariables) -> str:
        run_root = os.path.join(rtvars.gamer_path, 'regression_test', 'run')
        return os.path.join(run_root, self.test_id)

    # Canonicalization + stable digest helpers
    @staticmethod
    def _canonicalize(value):
        # Convert to a structure with deterministic ordering
        if value is None or isinstance(value, (int, float, str, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): TestCase._canonicalize(value[k]) for k in sorted(value.keys(), key=str)}
        if isinstance(value, (list, tuple)):
            return [TestCase._canonicalize(v) for v in value]
        if is_dataclass(value):  # Only accept frozen dataclasses
            cls = type(value)
            params = getattr(cls, "__dataclass_params__", None)
            if params is not None and getattr(params, "frozen", False):
                return {f.name: TestCase._canonicalize(getattr(value, f.name)) for f in fields(value)}
            raise TypeError(f"Cannot canonicalize dataclass {cls.__name__}: not frozen")
        raise TypeError(f"Cannot canonicalize value of type {type(value)}: {value}")

    def _stable_hexdigest(self) -> str:
        # 8-hex fingerprint (4-byte blake2s)
        payload = json.dumps(TestCase._canonicalize(self), separators=(",", ":"), sort_keys=True)
        return hashlib.blake2s(payload.encode("utf-8"), digest_size=4).hexdigest()

    def __hash__(self):
        return hash(self._stable_hexdigest())

    def __str__(self):
        return f"TestCase<{self.test_id}>"

    @property
    def test_id(self) -> str:
        """Unique identity for the test case, constructed from its content."""
        case_name = f"case_{self._stable_hexdigest()}" if self._case_name is None else self._case_name
        return os.path.join(self.path, case_name)

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

        fields['priority'] = priority2int(get_attr(attrs, 'priority', 0, (int, str)))
        fields['levels'] = get_attr(attrs, 'levels', {}, dict)

        references: List[TestReference] = []
        for ref in get_attr(attrs, 'references', [], list):
            references.append(TestReference(
                name=ref['name'],
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
        fields['_case_name'] = get_attr(attrs, 'name', None, str)

        # Construct TestCase instance and check duplicated test_id
        tc = TestCase(**fields)
        test_id = tc.test_id
        if test_id in TestCase._all_test_ids:
            raise ValueError(f"Duplicate path/name found: {test_id}")
        TestCase._all_test_ids.add(test_id)

        return tc
