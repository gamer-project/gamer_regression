import logging
import subprocess
import threading
from typing import Optional, Sequence, Union
from .logging_center import set_log_context, get_log_context


class _StreamLogger(threading.Thread):
    """Read from a binary stream, decode lines, and emit to logging with minimal overhead.

    Optionally tee output to a file path.
    """

    def __init__(self, stream, logger: logging.Logger, level: int,
                 tee_path: Optional[str] = None, name: str = "_StreamLogger"):
        super().__init__(name=name)
        self.daemon = True
        self._stream = stream
        self._logger = logger
        self._level = level
        self._tee_fp = open(tee_path, "ab", buffering=0) if tee_path else None
        self._stop_evt = threading.Event()
        # Capture context at construction time from parent thread
        self._ctx = get_log_context()

    def run(self):
        # Apply captured context into this thread
        set_log_context(test_id=self._ctx.get("test_id"), phase=self._ctx.get("phase"))
        while not self._stop_evt.is_set():
            chunk = self._stream.readline()
            if not chunk:
                break
            if self._tee_fp is not None:
                try:
                    self._tee_fp.write(chunk)
                except Exception:
                    pass
            # Decode and strip trailing newlines; keep errors safe
            try:
                line = chunk.decode(errors='replace').rstrip('\n')
            except Exception:
                line = str(chunk).rstrip('\n')
            if line:
                self._logger.log(self._level, line)
        if self._tee_fp is not None:
            try:
                self._tee_fp.flush()
                self._tee_fp.close()
            except Exception:
                pass

    def stop(self):
        self._stop_evt.set()


def run_process(cmd: Union[str, Sequence[str]], level: int = logging.DEBUG,
                cwd: Optional[str] = None, env: Optional[dict] = None, shell: bool = False,
                merge_streams: bool = False, tee_stdout: Optional[str] = None,
                tee_stderr: Optional[str] = None, check: bool = True) -> int:
    """Run a subprocess and stream stdout/stderr into logging in near real time.

    Returns the exit code; raises CalledProcessError if check=True and code!=0.
    """
    logger = logging.getLogger('process_runner')
    popen_kwargs = dict(cwd=cwd, env=env, shell=shell)
    if merge_streams:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **popen_kwargs)
        assert p.stdout is not None
        out_thread = _StreamLogger(p.stdout, logger, level, tee_path=tee_stdout, name="stdout")
        out_thread.start()
        p.wait()
        out_thread.join()
    else:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs)
        assert p.stdout is not None and p.stderr is not None
        out_thread = _StreamLogger(p.stdout, logger, level, tee_path=tee_stdout, name="stdout")
        err_thread = _StreamLogger(p.stderr, logger, level, tee_path=tee_stderr, name="stderr")
        out_thread.start()
        err_thread.start()
        p.wait()
        out_thread.join()
        err_thread.join()

    if check and p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd)
    return p.returncode
