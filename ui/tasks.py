"""Background execution helpers.

ADB and Fastboot calls block for anywhere between 30 ms and 30 s. Running
them on the GUI thread freezes the window, so every device operation is
dispatched to a :class:`QThreadPool` worker and reports back to the UI
through queued signals.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
)


class _TaskSignals(QObject):
    finished = Signal(object)   # result of the callable
    failed = Signal(str)        # traceback / error message


class _Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], args: tuple, kwargs: dict):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _TaskSignals()
        # Python owns the lifetime: letting QThreadPool delete the C++
        # object while run() is still unwinding kills the signal emitter
        # ("Internal C++ object (_TaskSignals) already deleted").
        self.setAutoDelete(False)

    def run(self) -> None:  # noqa: D102
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as error:  # noqa: BLE001 - reported to the UI
            import traceback

            self._emit(self.signals.failed, f"{error}\n\n{traceback.format_exc()}")
            return
        self._emit(self.signals.finished, result)

    @staticmethod
    def _emit(signal, payload) -> None:
        """Emit unless the window (and the signal object) is already gone."""
        try:
            signal.emit(payload)
        except RuntimeError:
            # application shut down while the worker was still running
            pass


class TaskRunner(QObject):
    """Small facade over ``QThreadPool`` with an activity counter."""

    busy_changed = Signal(bool)

    def __init__(self, parent=None, max_threads: int = 4):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max_threads)
        self._active = 0
        self._tasks: list = []

        # let running workers finish before the interpreter tears the
        # signal objects down
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._drain)

    # ---- api ----
    def run(
        self,
        fn: Callable[..., Any],
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        *args,
        quiet: bool = False,
        **kwargs,
    ) -> _Task:
        """Dispatch *fn* to the pool.

        ``quiet=True`` marks housekeeping work (periodic device polling) that
        must not raise the global busy indicator or the blocking overlay.
        """
        task = _Task(fn, args, kwargs)
        self._tasks.append(task)

        counted = not quiet
        if counted:
            self._active += 1
            if self._active == 1:
                self.busy_changed.emit(True)

        def _cleanup() -> None:
            if task in self._tasks:
                self._tasks.remove(task)
            if not counted:
                return
            self._active = max(0, self._active - 1)
            if self._active == 0:
                self.busy_changed.emit(False)

        if on_done is not None:
            task.signals.finished.connect(on_done)
        if on_error is not None:
            task.signals.failed.connect(on_error)
        task.signals.finished.connect(lambda _result: _cleanup())
        task.signals.failed.connect(lambda _msg: _cleanup())

        self.pool.start(task)
        return task

    @property
    def busy(self) -> bool:
        return self._active > 0

    def wait(self, timeout_ms: int = 5000) -> bool:
        return self.pool.waitForDone(timeout_ms)

    def _drain(self) -> None:
        self.pool.waitForDone(3000)
