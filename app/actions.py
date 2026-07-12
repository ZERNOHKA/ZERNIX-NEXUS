from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppAction:
    """Describe one UI action independently from its visual widget."""

    key: str
    title_key: str
    description_key: str
    button_key: str
    handler: Callable[[], object]
    category: str
    requires_admin: bool = False
    rollback_note: str = ""

    @classmethod
    def from_ui_row(
        cls,
        title_key: str,
        description_key: str,
        button_key: str,
        handler: Callable[[], object],
        *,
        category: str,
    ) -> "AppAction":
        return cls(
            key=title_key,
            title_key=title_key,
            description_key=description_key,
            button_key=button_key,
            handler=handler,
            category=category,
        )
