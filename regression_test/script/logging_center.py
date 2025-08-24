import contextvars
import logging
import logging.handlers
import queue
from typing import Optional, Iterable


# Context variables to enrich log records without passing loggers
_ctx_test_id: contextvars.ContextVar[str] = contextvars.ContextVar("test_id", default="-")
_ctx_phase: contextvars.ContextVar[str] = contextvars.ContextVar("phase", default="-")


class LoggingManager:
    """Singleton-like manager that wires QueueHandler on root and a QueueListener with real handlers."""

    _initialized = False
    _listener: Optional[logging.handlers.QueueListener] = None
    _queue: Optional[queue.Queue] = None
    _prev_record_factory = None

    @classmethod
    def setup(
        cls,
        handlers: Iterable[logging.Handler],
        level: int,
        queue_size: int = 10000,
    ) -> None:
        if cls._initialized:
            return

        # Install a LogRecord factory that injects context values at creation time (producer thread)
        cls._prev_record_factory = logging.getLogRecordFactory()

        def _record_factory(*args, **kwargs):
            record = cls._prev_record_factory(*args, **kwargs)
            if not hasattr(record, "test_id"):
                record.test_id = _ctx_test_id.get()
            if not hasattr(record, "phase"):
                record.phase = _ctx_phase.get()
            return record

        logging.setLogRecordFactory(_record_factory)

        # 1) Root gets a QueueHandler only
        cls._queue = queue.Queue(maxsize=queue_size)  # TODO: Change it to multiprocessing.Queue?
        qh = logging.handlers.QueueHandler(cls._queue)
        root = logging.getLogger()
        root.setLevel(level)
        # Ensure there are no pre-existing handlers to prevent duplicate output
        assert not root.handlers, "Root logger should have no handlers before setup"
        root.addHandler(qh)

        # 2) One listener thread that does formatting/I/O
        cls._listener = logging.handlers.QueueListener(cls._queue, *list(handlers), respect_handler_level=True)
        cls._listener.daemon = True
        cls._listener.start()

        # 3) Forward warnings into logging
        logging.captureWarnings(True)

        cls._initialized = True

    @classmethod
    def shutdown(cls) -> None:
        if cls._listener is not None:
            cls._listener.stop()
            cls._listener = None
        # Restore previous record factory
        if cls._prev_record_factory is not None:
            logging.setLogRecordFactory(cls._prev_record_factory)
            cls._prev_record_factory = None
        cls._initialized = False


def set_log_context(test_id: Optional[str] = None, phase: Optional[str] = None) -> None:
    """Set per-thread logging context fields; pass None to leave unchanged."""
    if test_id is not None:
        _ctx_test_id.set(test_id)
    if phase is not None:
        _ctx_phase.set(phase)


def clear_log_context() -> None:
    _ctx_test_id.set("-")
    _ctx_phase.set("-")


def get_log_context() -> dict:
    """Return a snapshot of current context values for propagation to worker threads."""
    return {"test_id": _ctx_test_id.get(), "phase": _ctx_phase.get()}


def log_init(log_file_path):
    """Initialize queue-based logging."""
    ROOT_LEVEL = logging.DEBUG
    CONSOLE_LEVEL = logging.DEBUG
    FILE_LEVEL = logging.DEBUG
    CONSOLE_FORMAT = '%(asctime)s : %(levelname)-8s %(name)-20s : %(message)s'
    FILE_FORMAT = '%(levelname)-8s %(name)-20s [%(test_id)s|%(phase)s] %(message)s'

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(CONSOLE_LEVEL)
    ch.setFormatter(logging.Formatter(CONSOLE_FORMAT))

    # File handler (more compact, but include context)
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(FILE_LEVEL)
    fh.setFormatter(logging.Formatter(FILE_FORMAT))

    LoggingManager.setup([ch, fh], level=ROOT_LEVEL)
