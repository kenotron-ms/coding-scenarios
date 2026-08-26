"""template_engine — a small, dependency-free template engine library.

Public surface
--------------
Template            Compile a source string; render it many times.
Environment         Composition root: loader, filters, defaults, cache.
TemplateError       Base exception class.
TemplateSyntaxError Raised at compile time with ``msg``, ``line``, ``col``.
TemplateRuntimeError Raised at render time.

Ambiguity resolutions (Sec.1.6)
--------------------------------
A-1 (undefined in lenient mode): empty string on interpolation, falsy in
    conditions, empty iteration in loops.
A-2 (whitespace): strict verbatim preservation.
A-3 (autoescape default): ``False`` on both ``Template`` and ``Environment``.
"""

__all__ = [
    "Template",
    "Environment",
    "TemplateError",
    "TemplateSyntaxError",
    "TemplateRuntimeError",
]

from .errors import TemplateError, TemplateSyntaxError, TemplateRuntimeError
from .environment import Environment, Template
