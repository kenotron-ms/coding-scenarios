"""Optional, best-effort validation of generated DOT against the attractor
engine's own ``parse_dot`` / ``validate`` (design doctrine, D3).

The ``attractor`` CLI is not always on PATH, and the engine module
(``amplifier_module_loop_pipeline``) is usually not pip-installed -- it ships
inside the ``amplifier-bundle-attractor`` cache. This module locates the engine
by trying, in order:

1. a normal import (if it happens to be installed / on PYTHONPATH);
2. the ``AMPLIFIER_LOOP_PIPELINE_DIR`` env var (points at the dir *containing*
   the ``amplifier_module_loop_pipeline`` package);
3. a glob of ``~/.amplifier/cache/*/modules/loop-pipeline``.

If none resolve, :class:`EngineUnavailable` is raised so callers/tests can skip
gracefully rather than fail. The generator itself never imports this module --
DOT generation is pure and engine-independent.
"""

from __future__ import annotations

import glob
import importlib
import os
import sys
from pathlib import Path


class EngineUnavailable(RuntimeError):
    """Raised when the attractor engine module cannot be located/imported."""


def _candidate_dirs() -> list[str]:
    dirs: list[str] = []
    env = os.environ.get("AMPLIFIER_LOOP_PIPELINE_DIR")
    if env:
        dirs.append(env)
    home = Path.home()
    dirs.extend(
        sorted(
            glob.glob(
                str(home / ".amplifier" / "cache" / "*" / "modules" / "loop-pipeline")
            )
        )
    )
    return dirs


def load_engine():
    """Return ``(parse_dot, validate)`` from the attractor engine, or raise
    :class:`EngineUnavailable`.
    """
    # 1. Already importable?
    try:
        dp = importlib.import_module("amplifier_module_loop_pipeline.dot_parser")
        vl = importlib.import_module("amplifier_module_loop_pipeline.validation")
        return dp.parse_dot, vl.validate
    except Exception:  # noqa: BLE001, S110 -- best-effort locator: any import failure just falls through to the cache-glob path
        pass

    # 2 & 3. Try candidate dirs on sys.path.
    for d in _candidate_dirs():
        pkg_init = Path(d) / "amplifier_module_loop_pipeline" / "__init__.py"
        if not pkg_init.is_file():
            continue
        if d not in sys.path:
            sys.path.insert(0, d)
        try:
            dp = importlib.import_module("amplifier_module_loop_pipeline.dot_parser")
            vl = importlib.import_module("amplifier_module_loop_pipeline.validation")
            return dp.parse_dot, vl.validate
        except Exception:  # noqa: BLE001, S112 -- try the next candidate dir on any failure
            continue

    raise EngineUnavailable(
        "attractor engine (amplifier_module_loop_pipeline) not found. "
        "Set AMPLIFIER_LOOP_PIPELINE_DIR to the dir containing the package, "
        "or install amplifier-bundle-attractor."
    )


def validate_dot_source(dot_source: str):
    """Parse ``dot_source`` and run engine validation.

    Returns ``(graph, diagnostics, error_count)`` where ``error_count`` is the
    number of ERROR-severity diagnostics. Raises :class:`EngineUnavailable` if
    the engine cannot be loaded, or ``ValueError`` if the source does not parse.
    """
    parse_dot, validate = load_engine()
    graph = parse_dot(dot_source)
    diagnostics = validate(graph)
    error_count = sum(1 for d in diagnostics if getattr(d, "severity", "") == "ERROR")
    return graph, diagnostics, error_count
