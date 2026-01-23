from __future__ import annotations

import contextlib
import contextvars
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterator


ProgressMode = str  # "auto" | "always" | "never"


def _now() -> float:
    return time.monotonic()


@dataclass
class _PhaseTiming:
    name: str
    started_at: float
    ended_at: float | None = None


class ProgressTask:
    def __init__(self, reporter: "_Reporter", name: str, total: int | None, unit: str) -> None:
        self._reporter = reporter
        self._name = name
        self._unit = unit
        self._total = total
        self._done = 0
        self._started_at = _now()

    def set_total(self, total: int | None) -> None:
        self._total = total
        self._reporter._maybe_render(task=self)

    def set_description(self, text: str) -> None:
        self._name = text
        self._reporter._maybe_render(task=self)

    def advance(self, n: int = 1) -> None:
        if n <= 0:
            return
        self._done += n
        self._reporter._maybe_render(task=self)

    @property
    def name(self) -> str:
        return self._name

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def total(self) -> int | None:
        return self._total

    @property
    def done(self) -> int:
        return self._done

    @property
    def started_at(self) -> float:
        return self._started_at


class _Reporter:
    def __init__(self, *, stream: Any, log_every_s: float, enabled: bool, quiet: bool) -> None:
        self._stream = stream
        self._log_every_s = float(log_every_s)
        self._enabled = bool(enabled)
        self._quiet = bool(quiet)
        self._last_render_at = 0.0
        self._active_phase: str | None = None

    def _write_line(self, text: str) -> None:
        try:
            self._stream.write(text + "\n")
            self._stream.flush()
        except Exception:
            pass

    def _maybe_render(self, *, task: ProgressTask) -> None:
        if not self._enabled:
            return
        if self._quiet:
            return
        now = _now()
        if self._log_every_s > 0 and (now - self._last_render_at) < self._log_every_s:
            return
        self._last_render_at = now

        elapsed = max(0.000001, now - task.started_at)
        rate = task.done / elapsed
        total = task.total
        if total is None:
            self._write_line(
                f"progress task={task.name} done={task.done} unit={task.unit} rate={rate:.2f}/{task.unit}/s"
            )
        else:
            pct = (task.done / total) * 100.0 if total > 0 else 0.0
            self._write_line(
                f"progress task={task.name} done={task.done} total={total} unit={task.unit} pct={pct:.1f} rate={rate:.2f}/{task.unit}/s"
            )

    @contextlib.contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if self._enabled and not self._quiet:
            self._write_line(f"phase start name={name}")
        self._active_phase = name
        try:
            yield
        finally:
            if self._enabled and not self._quiet:
                self._write_line(f"phase end name={name}")
            self._active_phase = None


class _NullReporter(_Reporter):
    def __init__(self) -> None:
        super().__init__(stream=sys.stderr, log_every_s=1e9, enabled=False, quiet=True)

    def _maybe_render(self, *, task: ProgressTask) -> None:
        return

    @contextlib.contextmanager
    def phase(self, name: str) -> Iterator[None]:
        yield


class _InteractiveReporter(_Reporter):
    def __init__(self, *, stream: Any, log_every_s: float, quiet: bool) -> None:
        super().__init__(stream=stream, log_every_s=log_every_s, enabled=True, quiet=quiet)
        self._in_task_line = False

    def _write_overwrite(self, text: str) -> None:
        try:
            self._stream.write("\r" + text + " " * 8)
            self._stream.flush()
            self._in_task_line = True
        except Exception:
            pass

    def _write_line(self, text: str) -> None:
        try:
            if self._in_task_line:
                self._stream.write("\n")
                self._in_task_line = False
            self._stream.write(text + "\n")
            self._stream.flush()
        except Exception:
            pass

    def _maybe_render(self, *, task: ProgressTask) -> None:
        if not self._enabled:
            return
        if self._quiet:
            return
        now = _now()
        if self._log_every_s > 0 and (now - self._last_render_at) < self._log_every_s:
            return
        self._last_render_at = now

        elapsed = max(0.000001, now - task.started_at)
        rate = task.done / elapsed
        total = task.total
        if total is None:
            self._write_overwrite(f"{task.name}: {task.done} {task.unit} ({rate:.2f}/{task.unit}/s)")
        else:
            pct = (task.done / total) * 100.0 if total > 0 else 0.0
            self._write_overwrite(f"{task.name}: {task.done}/{total} {task.unit} ({pct:.1f}%, {rate:.2f}/{task.unit}/s)")

    @contextlib.contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if self._enabled and not self._quiet:
            self._write_line(f"[phase] {name}")
        self._active_phase = name
        try:
            yield
        finally:
            if self._in_task_line:
                self._write_line("")
            self._active_phase = None


_reporter_var: contextvars.ContextVar[_Reporter] = contextvars.ContextVar("healthdelta_reporter", default=_NullReporter())
_phase_timings_var: contextvars.ContextVar[list[_PhaseTiming]] = contextvars.ContextVar("healthdelta_phase_timings", default=[])


class Progress:
    def configure(self, *, mode: ProgressMode = "auto", log_every_s: float = 5.0, quiet: bool = False) -> None:
        mode = (mode or "auto").strip().lower()
        if mode not in {"auto", "always", "never"}:
            raise ValueError("--progress must be one of: auto, always, never")

        stream = sys.stderr
        is_tty = bool(getattr(stream, "isatty", lambda: False)())
        enabled = mode != "never"

        reporter: _Reporter
        if not enabled:
            reporter = _NullReporter()
        else:
            if is_tty:
                reporter = _InteractiveReporter(stream=stream, log_every_s=0.1, quiet=quiet)
            else:
                reporter = _Reporter(stream=stream, log_every_s=float(log_every_s), enabled=True, quiet=quiet)

        _reporter_var.set(reporter)
        _phase_timings_var.set([])

    @contextlib.contextmanager
    def phase(self, name: str) -> Iterator[None]:
        timings = list(_phase_timings_var.get())
        t = _PhaseTiming(name=name, started_at=_now())
        timings.append(t)
        _phase_timings_var.set(timings)
        with _reporter_var.get().phase(name):
            try:
                yield
            finally:
                t.ended_at = _now()

    def task(self, name: str, total: int | None = None, unit: str = "items") -> ProgressTask:
        return ProgressTask(_reporter_var.get(), name=name, total=total, unit=unit)

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"phases": []}
        for t in _phase_timings_var.get():
            if t.ended_at is None:
                continue
            out["phases"].append({"name": t.name, "elapsed_s": round(t.ended_at - t.started_at, 3)})
        return out

    def print_summary(self) -> None:
        rep = _reporter_var.get()
        s = self.summary()
        for ph in s.get("phases") or []:
            if isinstance(ph, dict) and isinstance(ph.get("name"), str):
                try:
                    sys.stderr.write(f"phase summary name={ph['name']} elapsed_s={ph.get('elapsed_s')}\n")
                except Exception:
                    pass
        try:
            sys.stderr.flush()
        except Exception:
            pass


progress = Progress()
