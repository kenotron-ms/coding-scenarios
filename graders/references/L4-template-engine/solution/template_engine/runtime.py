"""Runtime sentinels shared by the renderer and the filter registry (leaf).

The :data:`UNDEFINED` singleton represents a name that was absent from the
render context in **lenient** mode (REQUIREMENTS FR-7, A-1). It stringifies to
the empty string, is falsy, and iterates as empty -- so the lenient policy is
uniform across interpolation, conditions, and loop targets without special
cases scattered through the renderer. In strict mode the renderer raises rather
than producing this value.
"""

from __future__ import annotations

from collections.abc import Iterator


class Undefined:
    """Sentinel for a missing name under the lenient undefined policy (A-1)."""

    __slots__ = ()

    def __str__(self) -> str:
        return ""

    def __bool__(self) -> bool:
        return False

    def __iter__(self) -> Iterator[object]:
        return iter(())

    def __len__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "UNDEFINED"


UNDEFINED = Undefined()
