"""Reconcile a live Claude Code config directory against the repository layout.

No function here writes to a live config directory unless it is passed ``apply=True``.
"""

from __future__ import annotations

__all__ = ["actions", "diff", "inventory", "report", "settings_merge"]

VERSION = "2.0.0"
