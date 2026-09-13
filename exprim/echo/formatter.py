# echo/formatter.py
from __future__ import annotations
from .event import MAX_LEVEL_LEN, Event, EventType, Level
from time import localtime, strftime

class Formatter:
    """
    Turns a structured Event into a human-readable string for console/file output.
    The Logger never does string formatting — that is exclusively Formatter's job.

    Formatters are stateless. They receive an Event and return a string.
    Subclass and override format() to customize output style.

    Default output format:
        [HH:MM:SS] [LEVEL] [module] message
        [HH:MM:SS] [METRIC] name=value step=N
    """

    def format(self, event: Event) -> str:
        """
        Dispatch to the appropriate format method based on event_type.
        Returns a fully formatted string ready for output.
        Never raises — malformed events produce a fallback string.
        """
        try:
            if event.event_type == EventType.TEXT:
                return self.format_text(event)
            elif event.event_type == EventType.METRIC:
                return self.format_metric(event)
            elif event.event_type == EventType.SCOPE:
                return self.format_scope(event)
            else:
                return f"[{self._format_timestamp(event.timestamp)}] [UNKNOWN] {event}"
        except Exception as e:
            return f"[MALFORMED EVENT] {e} - raw: {event}"


    def format_text(self, event: Event) -> str:
        """
        Format a TEXT event into a human-readable log line.

        Example output:
            [14:32:01] [INFO ] [frame.lorenz] step complete
        """
        return f"[{self._format_timestamp(event.timestamp)}] [{self._format_level(event.level)}] [{self.format_scope(event)}] {event.message}"

    def format_metric(self, event: Event) -> str:
        """
        Format a METRIC event into a readable line.

        Example output:
            [14:32:01] [METRIC] reward=-12.340 loss=0.041 step=100
        """
        pairs = " ".join(
            f"{k}:{v:.4f} " if isinstance(v, float) else f"{k}:{v} "
            for k, v in event.payload.items()
        )
        step_str = f" step={event.step}" if event.step is not None else ""
        metric_label = "METRIC" + " " * (MAX_LEVEL_LEN - len("METRIC"))
        return (
            f"[{self._format_timestamp(event.timestamp)}] "
            f"[{metric_label}] "
            f"{pairs}"
            f"{step_str}"
        )

    def format_scope(self, event: Event) -> str:
        scope = event.payload.get("scope", "")
        action = event.payload.get("action", "enter")
        arrow = "->" if action == "enter" else "<-"
        scope_label = "SCOPE" + " " * (MAX_LEVEL_LEN - len("SCOPE"))
        return (
            f"[{self._format_timestamp(event.timestamp)}] "
            f"[{scope_label}] "
            f"{arrow} {scope}"
        )

    def _format_timestamp(self, timestamp: float) -> str:
        """
        Convert a Unix timestamp float to a readable time string.
        Default: HH:MM:SS
        """
        return strftime('%H:%M:%S', localtime(timestamp))

    def _format_level(self, level: Level) -> str:
        """
        Return a fixed-width string representation of a Level. Fixed width keeps console output column-aligned.
        Example:
            Level.INFO    → "INFO   "
            Level.WARNING → "WARNING"
            Level.DEBUG   → "DEBUG  "
        """
        return level.name + " " * (MAX_LEVEL_LEN - len(level.name))
