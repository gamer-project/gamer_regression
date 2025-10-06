import logging
import os
import shutil
from typing import Dict, Optional, Protocol
from .girder_inscript import girder_handler
from .models import TestCase
from .runtime_vars import RuntimeVariables
from .utilities import STATUS


class ReferenceError(RuntimeError):
    """Base exception for reference staging issues."""

    def __init__(self, message: str, status: int = STATUS.FAIL):
        super().__init__(message)
        self.status = status


class MissingReferenceError(ReferenceError):
    def __init__(self, message: str):
        super().__init__(message, STATUS.MISSING_FILE)


class ReferenceProvider(Protocol):
    """Ensure reference data is available for a given test case."""

    reference_root: str

    def fetch(self, case: TestCase) -> str:
        """Fetch all references for *case* and return the directory containing them."""
        ...

    def push(self, case: TestCase, run_dir: str) -> None:
        """Push test results from *run_dir* to the reference storage for *case*."""
        ...


class LocalReferenceProvider:
    def __init__(self, abs_base_dir: str):
        self.base_dir = os.path.abspath(abs_base_dir)

    @property
    def reference_root(self) -> str:
        return self.base_dir

    def fetch(self, case: TestCase) -> str:
        logger = logging.getLogger('reference.local')
        case_dir = os.path.join(self.base_dir, case.test_id)
        if not os.path.isdir(case_dir):
            raise MissingReferenceError(f"Local reference directory missing: {case_dir}")
        missing = [ref.name for ref in case.references
                   if not os.path.isfile(os.path.join(case_dir, ref.name))]
        if missing:
            raise MissingReferenceError(
                f"Missing reference files for {case.test_id}: {', '.join(missing)}")
        logger.debug("Using local references at %s", case_dir)
        return case_dir

    def push(self, case: TestCase, run_dir: str) -> None:
        logger = logging.getLogger('reference.local')
        case_dir = os.path.join(self.base_dir, case.test_id)
        os.makedirs(case_dir, exist_ok=True)
        
        for ref in case.references:
            src = os.path.join(run_dir, ref.name)
            dst = os.path.join(case_dir, ref.name)
            if not os.path.isfile(src):
                logger.warning(f"Source file not found for reference update: {src}")
                continue
            shutil.copy2(src, dst)
            logger.info(f"Updated local reference: {dst}")
        logger.info(f"Pushed references for {case.test_id} to {case_dir}")


class GirderReferenceProvider:
    def __init__(self, gamer_path: str):
        self.gamer_path = gamer_path
        self._gh: Optional[girder_handler] = None
        self._has_version_list = False
        self._folder_cache: Optional[Dict[str, dict]] = None

    @property
    def reference_root(self) -> str:
        return os.path.join(self.gamer_path, 'regression_test', 'references', 'cloud')

    def fetch(self, case: TestCase) -> str:
        logger = logging.getLogger('reference.girder')
        case_dir = os.path.join(self.reference_root, case.test_id)
        os.makedirs(case_dir, exist_ok=True)
        self._ensure_client()
        self._ensure_version_list()

        group_name = case.path.replace('/', '')
        case_folder = case._case_name or case.test_id.split(os.sep)[-1]
        ref_folder = self._resolve_latest_folder(group_name)

        files = self._resolve_file_nodes(ref_folder, case_folder, case)
        self._clean_case_dir(case_dir)

        for ref in case.references:
            node = files.get(ref.name)
            if node is None:
                raise MissingReferenceError(
                    f"Reference file not found in cloud: {case_folder}/{ref.name}")
            file_id = node['_id']
            logger.info("Downloading %s/%s/%s (id=%s) to %s",
                        ref_folder, case_folder, ref.name, file_id, case_dir)
            status = self._gh.download_file_by_id(file_id, case_dir)
            if status != STATUS.SUCCESS:
                raise ReferenceError(
                    f"Download failed for {case.test_id}:{ref.name}", status)

        logger.debug("Downloaded cloud references to %s", case_dir)
        return case_dir

    def _ensure_client(self) -> None:
        if self._gh is None:
            try:
                self._gh = girder_handler(self.gamer_path, self._folder_cache or {})
            except Exception as exc:
                raise ReferenceError(f"Failed to initialize Girder client: {exc}", STATUS.DOWNLOAD)
        self._folder_cache = getattr(self._gh, 'home_folder_dict', None)

    def _ensure_version_list(self) -> None:
        if not self._has_version_list:
            try:
                status = self._gh.download_compare_version_list()
            except Exception as exc:
                raise ReferenceError(
                    f"Failed to download compare version list: {exc}", STATUS.DOWNLOAD)
            if status != STATUS.SUCCESS:
                raise ReferenceError("compare_version_list download failed", status)
            self._has_version_list = True

    def _resolve_latest_folder(self, group_name: str) -> str:
        try:
            ver_latest = self._gh.get_latest_version(group_name)
        except Exception as exc:
            raise ReferenceError(
                f"Unable to resolve latest reference version for {group_name}: {exc}",
                STATUS.DOWNLOAD)
        if not ver_latest or 'time' not in ver_latest:
            raise ReferenceError(f"Invalid version info for {group_name}", STATUS.DOWNLOAD)
        ref_folder = f"{group_name}-{ver_latest['time']}"
        if not self._folder_cache or ref_folder not in self._folder_cache:
            raise MissingReferenceError(
                f"Reference version folder not found: {ref_folder}")
        return ref_folder

    def _resolve_file_nodes(self, ref_folder: str, case_folder: str,
                             case: TestCase) -> Dict[str, dict]:
        node = self._folder_cache.get(ref_folder, {})
        if case_folder not in node:
            raise MissingReferenceError(
                f"Case folder not found in cloud: {case_folder}")
        case_node = node[case_folder]
        if not isinstance(case_node, dict):
            raise ReferenceError(f"Invalid node structure for {case_folder}")
        return {name: data for name, data in case_node.items() if name != '_id'}

    def _clean_case_dir(self, case_dir: str) -> None:
        for entry in os.listdir(case_dir):
            entry_path = os.path.join(case_dir, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path)
            else:
                os.remove(entry_path)

    def push(self, case: TestCase, run_dir: str) -> None:
        logger = logging.getLogger('reference.girder')
        logger.warning(f"Cloud reference push not yet implemented for {case.test_id}")
        logger.info("Skipping reference update for cloud provider")


def get_provider(rtvars: RuntimeVariables) -> ReferenceProvider:
    DEFAULT_LOCAL_PATH = os.path.join('regression_test', 'references', 'local')
    loc = rtvars.reference_loc
    if ":" in loc:
        kind, payload = loc.split(":", 1)
    else:
        kind, payload = loc, ""
    kind = kind.strip()
    payload = payload.strip()

    if kind == "local":
        if not payload:
            payload = DEFAULT_LOCAL_PATH
        path = payload if os.path.isabs(payload) else os.path.join(rtvars.gamer_path, payload)
        return LocalReferenceProvider(path)
    elif kind == "cloud":
        return GirderReferenceProvider(rtvars.gamer_path)
    raise ValueError(f"Unknown reference location '{loc}'")
