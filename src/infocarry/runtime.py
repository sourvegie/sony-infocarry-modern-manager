"""Supported desktop runtime checks for the InfoCarry GUI."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Tuple


# The packaged desktop release is tested against the project environment built
# from Python 3.12.13 and Tcl/Tk 9.0.  Keep the guard explicit so the old
# macOS system Python 3.9/Tk 8.5 cannot silently launch a blank prototype
# window.
MIN_PYTHON: Tuple[int, int] = (3, 12)
MIN_TK: Tuple[int, int] = (9, 0)


class DesktopRuntimeError(RuntimeError):
    """Raised when the desktop UI is running on an unsupported runtime."""


@dataclass(frozen=True)
class DesktopRuntime:
    python_version: Tuple[int, int, int]
    tk_version: Tuple[int, int]

    @property
    def description(self) -> str:
        return (
            f"Python {self.python_version[0]}.{self.python_version[1]}."
            f"{self.python_version[2]} with Tcl/Tk "
            f"{self.tk_version[0]}.{self.tk_version[1]}"
        )


def _parse_version(value: object) -> Tuple[int, int]:
    text = str(value)
    parts = text.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError) as exc:
        raise DesktopRuntimeError(f"could not determine Tcl/Tk version from {value!r}") from exc


def check_desktop_runtime() -> DesktopRuntime:
    """Validate the Python/Tk runtime before creating a desktop window.

    The macOS system Python 3.9/Tk 8.5 combination is intentionally rejected:
    it is the source of the legacy blank-window and dialog problems observed
    during the prototype.  The supported desktop environment is the project
    Python 3.12.13 distribution with Tcl/Tk 9.0.
    """

    python_version = tuple(sys.version_info[:3])
    if python_version[:2] < MIN_PYTHON:
        raise DesktopRuntimeError(
            "The InfoCarry desktop requires Python 3.12 or newer. "
            f"This process is using Python {python_version[0]}.{python_version[1]}."
            f"{python_version[2]}. Use the project Python 3.12/Tk 9 runtime; "
            "the macOS system Python 3.9/Tk 8.5 is unsupported."
        )

    try:
        import tkinter

        tk_version = _parse_version(tkinter.TkVersion)
    except ImportError as exc:
        raise DesktopRuntimeError(
            "Tkinter is not installed. Install the project Python 3.12.13 "
            "distribution that bundles Tcl/Tk 9.0."
        ) from exc
    if tk_version < MIN_TK:
        raise DesktopRuntimeError(
            f"The InfoCarry desktop requires Tcl/Tk {MIN_TK[0]}.{MIN_TK[1]} or newer; "
            f"this process found Tcl/Tk {tk_version[0]}.{tk_version[1]}. "
            "The macOS system Tk 8.5 is unsupported. Use the project Python "
            "3.12/Tk 9 runtime."
        )
    return DesktopRuntime(python_version, tk_version)


__all__ = ["DesktopRuntime", "DesktopRuntimeError", "check_desktop_runtime"]
