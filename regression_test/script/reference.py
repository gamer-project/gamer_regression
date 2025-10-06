import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol, Optional
from .girder_inscript import girder_handler
from .models import TestReference, TestCase
from .runtime_vars import RuntimeVariables
from .utilities import STATUS


@dataclass
class FetchContext:
    gamer_abs_path: str
    yh_folder_dict: Optional[dict] = None
    gh_has_list: bool = False
    case: Optional[TestCase] = None


class ReferenceProvider(Protocol):
    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        """Fetch reference into dest_dir. Returns (STATUS, reason)."""
        ...

    def push(self, src_path: str, ref: TestReference, ctx: FetchContext) -> tuple[int, str]:
        """Push src_path to the location specified by ref. Returns (STATUS, reason)."""
        ...


class LocalReferenceProvider:
    def __init__(self, abs_base_dir: str):
        self.base_dir = os.path.abspath(abs_base_dir)

    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        logger = logging.getLogger('reference.local')
        assert ctx.case is not None, 'Missing case in FetchContext for local provider'
        case_ref_dir = os.path.join(self.base_dir, ctx.case.test_id)
        path = os.path.abspath(os.path.join(case_ref_dir, ref.name))
        if not os.path.exists(path):
            return STATUS.MISSING_FILE, f"Local reference missing: {path}"
        os.makedirs(dest_dir, exist_ok=True)
        target = os.path.join(dest_dir, ref.name)
        try:
            if os.path.exists(target):
                os.remove(target)
            logger.info("Linking %s --> %s" % (path, target))
            os.symlink(path, target)
            return STATUS.SUCCESS, ""
        except Exception as e:
            return STATUS.EXTERNAL, f"Can not link file {path}: {e}"

    def push(self, src_path: str, ref: TestReference, ctx: FetchContext) -> tuple[int, str]:
        raise NotImplementedError("Push not implemented for LocalReferenceProvider")


class GirderReferenceProvider:
    def __init__(self):
        self.gh = None

    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        logger = logging.getLogger('reference.girder')
        status = STATUS.SUCCESS
        reason = ""
        os.makedirs(dest_dir, exist_ok=True)

        if self.gh is None:
            try:
                self.gh = girder_handler(ctx.gamer_abs_path, ctx.yh_folder_dict or {})
            except Exception:
                return STATUS.DOWNLOAD, 'Download from girder fails (init)'

        try:
            if not ctx.gh_has_list:
                status = self.gh.download_compare_version_list()
                if status != STATUS.SUCCESS:
                    return status, 'Download from girder fails (list)'
        except Exception:
            return STATUS.DOWNLOAD, 'Download from girder fails (list-exception)'

        if ctx.case is None:
            return STATUS.FAIL, 'Missing case in FetchContext for cloud provider'

        # Cloud group name (legacy): <TestName>_<Type>
        group_name = ctx.case.path.replace('/', '')
        case_folder = ctx.case._case_name  # Use the private field for supporting the legacy structure
        file_basename = ref.name

        # Resolve latest version folder
        ver_latest = self.gh.get_latest_version(group_name)
        ref_folder = f"{group_name}-{ver_latest['time']}"

        # Walk to case folder then file item
        node = self.gh.home_folder_dict.get(ref_folder)
        if node is None:
            return STATUS.DOWNLOAD, f"Reference version folder not found: {ref_folder}"
        if case_folder not in node:
            return STATUS.DOWNLOAD, f"Case folder not found in cloud: {case_folder}"
        node = node[case_folder]
        if file_basename not in node:
            return STATUS.DOWNLOAD, f"Reference file not found in cloud: {case_folder}/{file_basename}"
        file_id = node[file_basename]['_id']

        logger.info("Downloading (name: %s/%s/%s, id: %s) --> %s" %
                    (ref_folder, case_folder, file_basename, file_id, dest_dir))
        status = self.gh.download_file_by_id(file_id, dest_dir)
        if status != STATUS.SUCCESS:
            reason = 'Download failed'
        return status, reason

    def push(self, src_path: str, ref: TestReference, ctx: FetchContext) -> tuple[int, str]:
        raise NotImplementedError("Push not implemented for GirderReferenceProvider")


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
        return GirderReferenceProvider()
    raise ValueError(f"Unknown reference location '{loc}'")
