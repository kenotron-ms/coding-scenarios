"""template_engine -- a dependency-free text/HTML template library.

Public surface (REQUIREMENTS Sec.2.1): :class:`Template` and :class:`Environment`
for compiling and rendering, and the exception taxonomy (:class:`TemplateError`
and its subclasses). Importing the package has no side effects beyond defining
these names.

Reference solution for scenario L4-template-engine. It exists to sanity-check the
grader: it MUST pass the acceptance gate (>= 95%) and score cleanly, while the
sibling ``reference/solution_broken/`` fails it (HARNESS.md Sec.5).
"""

from __future__ import annotations

from .environment import Environment
from .errors import TemplateError, TemplateRuntimeError, TemplateSyntaxError
from .template import Template

__all__ = [
    "Environment",
    "Template",
    "TemplateError",
    "TemplateRuntimeError",
    "TemplateSyntaxError",
]
