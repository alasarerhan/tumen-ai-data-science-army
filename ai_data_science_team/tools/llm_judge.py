from __future__ import annotations

"""f6_llm_judge. Deterministic LLM-as-Judge tools. Pure-Python
scoring for agent outputs (correctness, faithfulness, code
quality) without an LLM dependency; the agent layer is expected
to delegate to a real LLM when available, while this tool
implements the deterministic contract end-to-end.
"""

import re  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Sequence, Tuple  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


_NUM_RE = re.compile(r"\b\d+([.,]\d+)?%?\b")
_CODE_FENCE = re.compile(r"```")
_TABLE_ROW = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
_HEDGE = re.compile(
    r"\b(maybe|perhaps|might be|i think|i guess|"
    r"not sure|somewhat|kind of|sort of)\b",
    re.IGNORECASE,
)


def _score_length(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    if n < 50:
        return 0.3
    if n > 10000:
        return 0.6
    if 200 <= n <= 4000:
        return 1.0
    return 0.8


def _score_structure(text: str) -> float:
    if not text:
        return 0.0
    has_fence = bool(_CODE_FENCE.search(text))
    has_table = bool(_TABLE_ROW.search(text))
    has_numbers = bool(_NUM_RE.search(text))
    score = 0.2  # baseline for non-empty
    if has_fence:
        score += 0.3
    if has_table:
        score += 0.2
    if has_numbers:
        score += 0.2
    return min(score, 1.0)


def _score_faithfulness(text: str) -> float:
    if not text:
        return 0.0
    hedges = len(_HEDGE.findall(text))
    n = max(len(text), 1)
    hedge_density = hedges / (n / 200)  # hedges per ~200 chars
    # Lower is better.  0 → 1.0, 5+ → ~0.0
    if hedge_density <= 0:
        return 1.0
    if hedge_density >= 5:
        return 0.0
    return max(0.0, 1.0 - 0.2 * hedge_density)


# ---------------------------------------------------------------------------
# Code-quality helper
# ---------------------------------------------------------------------------


def _code_quality(code: str) -> float:
    if not code:
        return 0.5
    score = 0.5
    lines = code.splitlines()
    if lines:
        avg = sum(len(line) for line in lines) / max(len(lines), 1)
        if avg > 120:
            score -= 0.2
        if any(line.strip().endswith(":") for line in lines):
            score += 0.1
        if "def " in code or "class " in code:
            score += 0.1
    if "try:" in code and "except" in code:
        score += 0.1
    return max(0.0, min(score, 1.0))


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


@dataclass
class JudgeScore:
    correctness: float
    faithfulness: float
    code_quality: float
    overall: float
    recommendation: str  # "accept" | "revise" | "reject"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correctness": round(self.correctness, 4),
            "faithfulness": round(self.faithfulness, 4),
            "code_quality": round(self.code_quality, 4),
            "overall": round(self.overall, 4),
            "recommendation": self.recommendation,
        }


def judge_output(
    text: str,
    code: str = "",
    *,
    weights: Tuple[float, float, float] = (0.5, 0.3, 0.2),
    accept_threshold: float = 0.70,
    revise_threshold: float = 0.50,
) -> JudgeScore:
    """Score an agent's output.

    The deterministic core weighs three signals: length/structure
    proxy (correctness), hedge density (faithfulness), and a
    crude code-quality check on an optional code block.  The
    agent layer is expected to override this with a real LLM
    call when one is configured.
    """
    correctness = 0.6 * _score_length(text) + 0.4 * _score_structure(text)
    faithfulness = _score_faithfulness(text)
    code_q = _code_quality(code)
    overall = (
        weights[0] * correctness
        + weights[1] * faithfulness
        + weights[2] * code_q
    )
    if overall >= accept_threshold:
        rec = "accept"
    elif overall >= revise_threshold:
        rec = "revise"
    else:
        rec = "reject"
    return JudgeScore(
        correctness=correctness,
        faithfulness=faithfulness,
        code_quality=code_q,
        overall=overall,
        recommendation=rec,
    )


def judge_batch(
    items: Sequence[Mapping[str, str]],
    *,
    weights: Tuple[float, float, float] = (0.5, 0.3, 0.2),
    accept_threshold: float = 0.70,
    revise_threshold: float = 0.50,
) -> List[JudgeScore]:
    """Score a batch of {text, code} dicts."""
    return [
        judge_output(
            item.get("text", ""),
            item.get("code", ""),
            weights=weights,
            accept_threshold=accept_threshold,
            revise_threshold=revise_threshold,
        )
        for item in items
    ]


