"""f4_model_card. Deterministic model-card tools supporting the F4
spec.  Pure-Python model-card generator with versioned sections
plus optional PDF rendering (WeasyPrint is an optional
dependency; HTML output is the default when unavailable).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


CARD_SECTIONS: tuple = (
    "model_details",
    "intended_use",
    "training_data",
    "features",
    "metrics",
    "fairness",
    "lineage",
    "limitations",
)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()

@dataclass
class CardSection:
    name: str
    content: str = ""
    is_draft: bool = False
    last_updated: float = field(default_factory=_now)


@dataclass
class ModelCard:
    model_id: str
    card_id: str = field(default_factory=_new_id)
    version: int = 1
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    sections: Dict[str, CardSection] = field(default_factory=dict)
    draft: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "card_id": self.card_id,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "draft": self.draft,
            "sections": {k: {"content": v.content, "is_draft": v.is_draft,
                              "last_updated": v.last_updated}
                         for k, v in self.sections.items()},
        }


CARD_REGISTRY: Dict[str, ModelCard] = {}


def generate_card(
    model_id: str,
    *,
    details: Optional[Dict[str, Any]] = None,
    intended_use: str = "",
    training_data: Dict[str, Any] | None = None,
    features: List[str] | None = None,
    metrics: Dict[str, float] | None = None,
    fairness: Dict[str, Any] | None = None,
    lineage: List[str] | None = None,
    limitations: str = "",
) -> ModelCard:
    """Generate a fresh model card with default section shells."""
    card = ModelCard(model_id=model_id)
    now = _now()
    for name in CARD_SECTIONS:
        card.sections[name] = CardSection(name=name, last_updated=now)
    if details:
        card.sections["model_details"].content = _fmt_mapping(details)
    if intended_use:
        card.sections["intended_use"].content = intended_use
    if training_data:
        card.sections["training_data"].content = _fmt_mapping(training_data)
    if features:
        card.sections["features"].content = "\n".join(
            f"- {f}" for f in features
        )
    if metrics:
        card.sections["metrics"].content = _fmt_metrics(metrics)
    if fairness:
        card.sections["fairness"].content = _fmt_mapping(fairness)
    if lineage:
        card.sections["lineage"].content = "\n".join(
            f"- {a}" for a in lineage
        )
    if limitations:
        card.sections["limitations"].content = limitations
        card.sections["limitations"].is_draft = True
    CARD_REGISTRY[card.card_id] = card
    return card


def _fmt_mapping(d: Mapping[str, Any]) -> str:
    lines = []
    for k, v in d.items():
        if isinstance(v, Mapping):
            lines.append(f"**{k}**")
            for kk, vv in v.items():
                lines.append(f"  - {kk}: {vv}")
        else:
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)


def _fmt_metrics(m: Mapping[str, float]) -> str:
    return "\n".join(f"- **{k}**: {v:.4f}" for k, v in m.items())


def update_section(
    card: ModelCard,
    section: str,
    content: str,
    *,
    is_draft: bool = False,
    increment_version: bool = True,
) -> ModelCard:
    """Update or insert a section on a card.

    Returns the **new** version of the card (or the same card if
    ``increment_version=False``).  The original card is left
    unchanged so the registry retains the full history.
    """
    if section not in CARD_SECTIONS:
        raise KeyError(f"unknown section {section!r}; expected one of {CARD_SECTIONS}")
    new_card = ModelCard(
        model_id=card.model_id,
        card_id=card.card_id,
        version=card.version + 1 if increment_version else card.version,
        created_at=card.created_at,
        updated_at=_now(),
        draft=is_draft,
        sections={
            k: CardSection(
                name=v.name,
                content=v.content,
                is_draft=v.is_draft,
                last_updated=v.last_updated,
            )
            for k, v in card.sections.items()
        },
    )
    new_card.sections[section] = CardSection(
        name=section, content=content, is_draft=is_draft,
        last_updated=_now(),
    )
    CARD_REGISTRY[new_card.card_id] = new_card
    return new_card


def render_html(card: ModelCard) -> str:
    """Render the card as a stand-alone HTML document."""
    parts = [
        f"<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>Model Card — {card.model_id} v{card.version}</title>",
        "<style>body{font-family:sans-serif;max-width:780px;margin:2em auto}",
        "h1{font-size:1.6em}h2{margin-top:1.4em;border-bottom:1px solid #ccc}",
        "code{background:#f4f4f4;padding:2px 4px}</style></head><body>",
        f"<h1>Model Card — {card.model_id} v{card.version}</h1>",
    ]
    if card.draft:
        parts.append("<p><em>(DRAFT — pending human review)</em></p>")
    for name in CARD_SECTIONS:
        section = card.sections.get(name)
        if not section or not section.content:
            continue
        heading = name.replace("_", " ").title()
        marker = " (draft)" if section.is_draft else ""
        parts.append(f"<h2>{heading}{marker}</h2>")
        body = section.content.replace("\n", "<br>")
        parts.append(f"<p>{body}</p>")
    parts.append("</body></html>")
    return "".join(parts)


def render_pdf(card: ModelCard) -> bytes:
    """Render PDF if WeasyPrint is available, else return HTML bytes
    as a safe fallback (the caller can persist as .html)."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return render_html(card).encode("utf-8")
    return HTML(string=render_html(card)).write_pdf()


def get_card(card_id: str) -> ModelCard:
    if card_id not in CARD_REGISTRY:
        raise KeyError(f"no card with id {card_id!r}")
    return CARD_REGISTRY[card_id]


def list_cards(model_id: str) -> List[ModelCard]:
    return [c for c in CARD_REGISTRY.values() if c.model_id == model_id]


F4_MODEL_CARD_TOOL_NAMES: List[str] = [
    "f4_generate_card",
    "f4_update_section",
    "f4_render_html",
    "f4_render_pdf",
    "f4_list_cards",
]
