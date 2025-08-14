import os
import subprocess
from dataclasses import dataclass
from typing import Protocol, Optional

from .models import TestReference, TestCase
from .utilities import set_up_logger, STATUS
import script.girder_inscript as gi


@dataclass
class FetchContext:
    gamer_abs_path: str
    logger_name: str
    ch: object
    file_handler: object
    yh_folder_dict: Optional[dict] = None
    gh_has_list: bool = False
    case: Optional[TestCase] = None


class ReferenceProvider(Protocol):
    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        """Fetch reference into dest_dir. Returns (STATUS, reason)."""
        ...


class LocalReferenceProvider:
    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        logger = set_up_logger(ctx.logger_name + ":ref-local", ctx.ch, ctx.file_handler)
        _, path = ref.loc.split(":", 1)
        os.makedirs(dest_dir, exist_ok=True)
        target = os.path.join(dest_dir, os.path.basename(path))
        try:
            if os.path.islink(target) or os.path.exists(target):
                return STATUS.SUCCESS, ""
            logger.info("Linking %s --> %s" % (path, target))
            os.symlink(path, target)
            return STATUS.SUCCESS, ""
        except Exception as e:
            return STATUS.EXTERNAL, f"Can not link file {path}: {e}"


class GirderReferenceProvider:
    def __init__(self):
        self.gh = None

    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        logger = set_up_logger(ctx.logger_name + ":ref-cloud", ctx.ch, ctx.file_handler)
        status = STATUS.SUCCESS
        reason = ""
        os.makedirs(dest_dir, exist_ok=True)

        if self.gh is None:
            try:
                self.gh = gi.girder_handler(ctx.gamer_abs_path, set_up_logger(
                    'girder', ctx.ch, ctx.file_handler), ctx.yh_folder_dict or {})
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
        group_name = ctx.case.test_group
        case_folder = ctx.case.case_name
        # Determine the file name to fetch: prefer basename from declared reference name
        file_basename = os.path.basename(ref.name) if ref.name else os.path.basename(ref.loc.split(":", 1)[1])

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


class UrlReferenceProvider:
    def fetch(self, ref: TestReference, dest_dir: str, ctx: FetchContext) -> tuple[int, str]:
        logger = set_up_logger(ctx.logger_name + ":ref-url", ctx.ch, ctx.file_handler)
        _, url = ref.loc.split(":", 1)
        os.makedirs(dest_dir, exist_ok=True)
        target = os.path.join(dest_dir, os.path.basename(url))
        try:
            cmd = ["curl", "-L", url, "-o", target]
            logger.info("Downloading %s --> %s" % (url, target))
            subprocess.check_call(cmd)
            return STATUS.SUCCESS, ""
        except Exception as e:
            return STATUS.DOWNLOAD, f"Download from {url} failed: {e}"


def get_provider(loc: str) -> ReferenceProvider:
    where = loc.split(":", 1)[0]
    if where == "local":
        return LocalReferenceProvider()
    if where == "cloud":
        return GirderReferenceProvider()
    if where == "url":
        return UrlReferenceProvider()
    raise ValueError(f"Unknown reference location '{where}'")
