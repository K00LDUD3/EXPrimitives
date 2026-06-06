from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Generator

from .event import Event, Level, EventType
from .sinks import Sink, ConsoleSink
#from .formatter import Formatter


class Logger:
    """
    Primary API for Echo. This is the only class user code interacts with directly.

    One Logger instance per run. Pass it explicitly to any subsystem that needs
    to log — never use a global logger instance.

    Args:
        run_id:      identifier attached to every event this logger emits
        module:      dotted module name of the owning subsystem e.g. "frame.lorenz"
        sinks:       list of Sink instances to emit to
        min_level:   global minimum level — events below this are dropped
                     before reaching any sink
        silent:      if True, all emit calls are no-ops — zero I/O overhead
    """

    def __init__(
        self,
        run_id: str = "",
        module: str = "",
        sinks: list[Sink] | None = None,
        min_level: Level = Level.DEBUG,
        silent: bool = False,
    ) -> None:
        self.run_id = run_id
        self.module = module
        self.min_level = min_level
        self.silent = silent

        self._sinks: list[Sink] = sinks if sinks is not None else [ConsoleSink()]

        #_: step tracking — thread safe
        self._step: int | None = None
        self._step_lock = threading.Lock()

        #_: scope stack — thread safe
        self._scope_stack: list[str] = []
        self._scope_lock = threading.Lock()

        #_: stats counters
        self._stats: dict[str, int] = {
            "DEBUG": 0,
            "INFO": 0,
            "WARNING": 0,
            "ERROR": 0,
            "metric": 0,
            "dropped": 0,
        }
        self._stats_lock = threading.Lock()

        #_: throttle tracking: metric name -> last step it was emitted
        self._throttle_last: dict[str, int] = {}
        self._throttle_steps: dict[str, int] = {}
        self._throttle_lock = threading.Lock()

    #NOTE: core emit

    def emit(self, event: Event) -> None:
        """
        Route a fully constructed Event to all sinks.
        Respects silent mode and min_level.
        Single choke point all other methods funnel through.
        """
        if self.silent:
            with self._stats_lock:
                self._stats["dropped"] += 1
            return

        if event.level.value < self.min_level.value:
            with self._stats_lock:
                self._stats["dropped"] += 1
            return

        for sink in self._sinks:
            sink.emit(event)

        with self._stats_lock:
            if event.event_type == EventType.METRIC:
                self._stats["metric"] += 1
            else:
                self._stats[event.level.name] += 1

    #NOTE: text logging

    def debug(
        self,
        message: str,
        *,
        tags: tuple[str, ...] = (),
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a DEBUG level TEXT event."""
        self.emit(self._make_event(Level.DEBUG, EventType.TEXT, message, payload or {}, tags))

    def info(
        self,
        message: str,
        *,
        tags: tuple[str, ...] = (),
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit an INFO level TEXT event."""
        self.emit(self._make_event(Level.INFO, EventType.TEXT, message, payload or {}, tags))

    def warning(
        self,
        message: str,
        *,
        tags: tuple[str, ...] = (),
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a WARNING level TEXT event."""
        self.emit(self._make_event(Level.WARNING, EventType.TEXT, message, payload or {}, tags))

    def error(
        self,
        message: str,
        *,
        tags: tuple[str, ...] = (),
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit an ERROR level TEXT event."""
        self.emit(self._make_event(Level.ERROR, EventType.TEXT, message, payload or {}, tags))

    #NOTE: metric logging
    def metric(
        self,
        name: str,
        value: float,
        *,
        step: int | None = None,
        tags: tuple[str, ...] = (),
        throttle_steps: int | None = None,
    ) -> None:
        """
        Emit a METRIC event carrying a named numeric observation.

        Args:
            name:           metric name e.g. "reward", "loss", "control_effort"
            value:          numeric value
            step:           simulation or training step — overrides internal step if provided
            tags:           arbitrary labels for filtering
            throttle_steps: only emit this metric once every N steps
        """
        resolved_step = step if step is not None else self._step

        #_: register throttle if first time seeing this metric
        if throttle_steps is not None:
            with self._throttle_lock:
                self._throttle_steps[name] = throttle_steps

        if resolved_step is not None and self._should_throttle(name, resolved_step):
            with self._stats_lock:
                self._stats["dropped"] += 1
            return

        #_: record last emitted step
        if resolved_step is not None:
            with self._throttle_lock:
                self._throttle_last[name] = resolved_step

        payload = {"name": name, "value": value}
        event = self._make_event(
            Level.INFO,
            EventType.METRIC,
            name,
            payload,
            tags,
        )
        #_: override step on the event
        object.__setattr__(event, "step", resolved_step)
        self.emit(event)

    #NOTE: scope context manager
    @contextmanager
    def scope(self, name: str) -> Generator[None, None, None]:
        """
        Context manager that emits SCOPE entry and exit events and
        maintains an internal scope stack for nested scoping.

        Usage:
            with logger.scope("train_epoch"):
                logger.info("epoch started")
                with logger.scope("forward_pass"):
                    logger.debug("computing loss")
        """
        with self._scope_lock:
            self._scope_stack.append(name)
            current = self._current_scope()

        entry_event = self._make_event(
            Level.DEBUG,
            EventType.SCOPE,
            "",
            {"scope": current, "action": "enter"},
            (),
        )
        self.emit(entry_event)

        try:
            yield
        finally:
            exit_event = self._make_event(
                Level.DEBUG,
                EventType.SCOPE,
                "",
                {"scope": current, "action": "exit"},
                (),
            )
            self.emit(exit_event)

            with self._scope_lock:
                self._scope_stack.pop()

    #_: step tracking
    def set_step(self, step: int) -> None:
        """Set the current global step. Thread-safe."""
        with self._step_lock:
            self._step = step

    def increment_step(self) -> None:
        """Increment the internal step counter by one."""
        with self._step_lock:
            self._step = (self._step or 0) + 1

    #NOTE: child loggers
    def child(self, module: str) -> Logger:
        """
        Return a new Logger that shares this logger's sinks and run_id
        but carries a different module label.

        Usage:
            root  = Logger(run_id="abc", sinks=[console, file_sink])
            frame = root.child("frame.lorenz")
            guide = root.child("guide.pid")
        """
        return Logger(
            run_id = self.run_id,
            module = module,
            sinks = self._sinks,
            min_level = self.min_level,
            silent = self.silent,
        )

    #NOTE: lifecycle
    def stats(self) -> dict[str, int]:
        """Return emission statistics for this logger."""
        with self._stats_lock:
            return dict(self._stats)

    def flush(self) -> None:
        """Force all sinks to flush their buffers."""
        for sink in self._sinks:
            sink.flush()

    def close(self) -> None:
        """Flush and close all sinks. Do not use logger after calling this."""
        self.flush()
        for sink in self._sinks:
            sink.close()

    #NOTE: internal helpers

    def _make_event(
        self,
        level: Level,
        event_type: EventType,
        message: str,
        payload: dict[str, Any],
        tags: tuple[str, ...],
    ) -> Event:
        """Construct an Event with all logger-level context attached."""
        return Event.now(
            level = level,
            event_type = event_type,
            message = message,
            payload = payload,
            run_id = self.run_id,
            module = self.module or self._current_scope(),
            tags = tags,
            step = self._step,
        )

    def _current_scope(self) -> str:
        """Return the current scope stack as a ' > ' joined string."""
        return " > ".join(self._scope_stack)

    def _should_throttle(self, name: str, step: int) -> bool:
        """
        Return True if this metric should be suppressed at this step.
        Suppressed if fewer than throttle_steps have passed since last emit.
        """
        with self._throttle_lock:
            if name not in self._throttle_steps:
                return False
            interval = self._throttle_steps[name]
            last_step = self._throttle_last.get(name, -interval)
            return (step - last_step) < interval
