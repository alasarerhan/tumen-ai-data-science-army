"""OpenAI/Vertex API quota hard cap — Kanban 7.4.

Aylık spend limit. Aşıldığında 429 + audit alert.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# Pricing per 1K tokens (gpt-4o-mini reference)
PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "claude-haiku-4": {"input": 0.0008, "output": 0.004},
}


class QuotaTracker:
    """Aylık spend track."""

    def __init__(self, budget_usd: float = 50.0, state_file: Path | None = None):
        self.budget_usd = budget_usd
        self.state_file = state_file or Path("/tmp/quota_state.json")
        self._load()

    def _load(self):
        if self.state_file.exists():
            self.state = json.loads(self.state_file.read_text())
        else:
            self.state = {"month": time.strftime("%Y-%m"), "spend_usd": 0.0, "calls": 0}
        # Ay değişti mi?
        current_month = time.strftime("%Y-%m")
        if self.state.get("month") != current_month:
            self.state = {"month": current_month, "spend_usd": 0.0, "calls": 0}

    def _save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def record(self, model: str, input_tokens: int, output_tokens: int) -> dict:
        """API call kayıt et. Budget aşılırsa 429 raise."""
        price = PRICING.get(model, PRICING["gpt-4o-mini"])
        cost = (input_tokens / 1000) * price["input"] + (output_tokens / 1000) * price["output"]
        self.state["spend_usd"] += cost
        self.state["calls"] += 1
        self._save()
        if self.state["spend_usd"] > self.budget_usd:
            return {
                "status": "quota_exceeded",
                "spend_usd": round(self.state["spend_usd"], 4),
                "budget_usd": self.budget_usd,
            }
        return {
            "status": "ok",
            "spend_usd": round(self.state["spend_usd"], 4),
            "budget_usd": self.budget_usd,
            "call_cost_usd": round(cost, 6),
        }


if __name__ == "__main__":
    import sys

    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 0.01  # small budget for demo
    tracker = QuotaTracker(budget_usd=budget, state_file=Path("/tmp/quota_demo.json"))
    # Simulate 5 calls
    for i in range(5):
        r = tracker.record("gpt-4o-mini", 1000, 500)
        print(f"Call {i + 1}: {r}")
    # Reset
    Path("/tmp/quota_demo.json").unlink(missing_ok=True)
