from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Principal:
    sub: str
    email: str | None
    claims: dict[str, Any]
