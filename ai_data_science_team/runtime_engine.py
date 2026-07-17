from __future__ import annotations

"""RuntimeEngine — resilient step-by-step workflow executor (M22).

Resilience patterns
-------------------
* **Retry + exponential back-off**: each step is retried up to
  ``max_retries`` times with sleep of ``backoff_base * 2 ** attempt``
  seconds before trying fallback agents.
* **Fallback chain**: when all retries for the primary agent fail, the
  engine automatically tries the agents listed in ``step["fallbacks"]``
  using the same retry policy.
* **Circuit breaker**: an agent that accumulates ``cb_threshold`` or more
  consecutive failures in the current session is marked *open*.  Open
  agents are skipped for the remainder of the run.
* **Checkpoint / resume**: the engine stores completed step results in
  the provided ``ContextStore`` under the ``"_checkpoint"`` key after
  each successful step so that a restarted run can skip already-completed
  steps.
* **Graceful degradation**: when ``graceful_degradation=True`` (default),
  a permanently failed step is logged and execution continues with remaining
  steps instead of aborting.
* **WorkflowSignal polling**: the engine polls ``SignalStore.pop_pending()``
  before every step to check for PAUSE / SKIP / CANCEL / MODIFY / ANNOTATE
  signals emitted by the user during the run.

Usage
-----
::

    from ai_data_science_team.runtime_engine import RuntimeEngine, RunResult  # noqa: E402, F401

    def my_executor(agent_name: str, instruction: str, context: dict):
        # Instantiate and invoke the agent; raise on failure
        agent = MyAgentClass(model=llm)
        result = agent.invoke_agent(user_instructions=instruction)
        return result.get_artifacts()

    engine = RuntimeEngine(agent_executor=my_executor)
    run_result: RunResult = engine.run(
        spec=workflow_spec,
        session_id="session-42",
        scenario="supervised",
    )
    logger.info(run_result.status)          # "completed" | "degraded" | "cancelled"
    logger.info(run_result.success_count)   # steps that succeeded
"""

import logging  # noqa: E402, F401
import time  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Callable, Dict, List, Optional  # noqa: E402, F401

from ai_data_science_team.signals import SignalStore, SignalType, get_signal_store  # noqa: E402, F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    """Execution result for a single workflow step.

    Attributes
    ----------
    step_id : str
        The step's id from the WorkflowSpec.
    agent_name : str
        The agent that ultimately ran this step (may be a fallback).
    status : str
        ``"success"`` | ``"skipped"`` | ``"failed"`` | ``"degraded"``.
    output : Any
        Return value from the agent executor (on success).
    error : str | None
        Last error message (on failure/skip with reason).
    retries : int
        Number of retry attempts consumed before the final outcome.
    duration_ms : float
        Wall-clock duration of the last successful or final attempt.
    """

    step_id: str
    agent_name: str
    status: str
    output: Any = None
    error: Optional[str] = None
    retries: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "error": self.error,
            "retries": self.retries,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class RunResult:
    """Aggregate result of a workflow run.

    Attributes
    ----------
    workflow_name : str
        Name from the WorkflowSpec.
    scenario : str
        One of ``"dynamic"`` / ``"supervised"`` / ``"manual"``.
    session_id : str
        Active session id.
    status : str
        ``"completed"`` | ``"degraded"`` | ``"cancelled"``.
    step_results : list[StepResult]
        Per-step results ordered by execution order.
    final_outputs : dict
        Mapping of step_id → step output (for successful steps).
    """

    workflow_name: str
    scenario: str
    session_id: str
    status: str = "completed"
    step_results: List[StepResult] = field(default_factory=list)
    final_outputs: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------- helpers

    @property
    def success_count(self) -> int:
        return sum(1 for s in self.step_results if s.status == "success")

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.step_results if s.status == "failed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for s in self.step_results if s.status == "skipped")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "scenario": self.scenario,
            "session_id": self.session_id,
            "status": self.status,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "steps": [s.to_dict() for s in self.step_results],
        }


# ---------------------------------------------------------------------------
# RuntimeEngine
# ---------------------------------------------------------------------------


class RuntimeEngine:
    """Executes a validated :data:`WorkflowSpec` step-by-step with resilience.

    Parameters
    ----------
    agent_executor : Callable[[str, str, dict], Any]
        A callable ``(agent_name, instruction, context) -> output`` that
        instantiates and invokes the named agent.  Must raise on failure.
        The *context* dict is shared across steps: completed step outputs
        are stored under their step id so downstream agents can read them.
    signal_store : SignalStore | None
        Source of user intervention signals.  Defaults to the global
        singleton so platform-wide signals are visible.
    context_store : Any | None
        Optional ``ContextStore`` instance used for checkpointing.
        Pass the same ``ContextStore`` used by the session for consistency.
    max_retries : int
        Maximum retries per step/agent before trying the next fallback.
    backoff_base : float
        Base sleep duration for exponential back-off (seconds).
    cb_threshold : int
        Consecutive failure count at which a circuit breaker opens.
    graceful_degradation : bool
        If True, permanently failed steps are logged but execution continues.
        If False, the first permanent failure sets ``run_result.status =
        "degraded"`` and exits the loop.
    """

    def __init__(
        self,
        agent_executor: Callable[[str, str, Dict[str, Any]], Any],
        signal_store: Optional[SignalStore] = None,
        context_store: Optional[Any] = None,
        max_retries: int = 2,
        backoff_base: float = 1.0,
        cb_threshold: int = 3,
        graceful_degradation: bool = True,
    ) -> None:
        self._execute = agent_executor
        self._signals = signal_store or get_signal_store()
        self._context_store = context_store
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.cb_threshold = cb_threshold
        self.graceful_degradation = graceful_degradation

        # { session_id: { agent_name: consecutive_failure_count } }
        self._cb_counters: Dict[str, Dict[str, int]] = {}

    # ------------------------------------------------------------------ public

    def run(
        self,
        spec: Dict[str, Any],
        session_id: str,
        scenario: str = "supervised",
        context: Optional[Dict[str, Any]] = None,
    ) -> RunResult:
        """Execute a WorkflowSpec and return a :class:`RunResult`.

        Parameters
        ----------
        spec : dict
            A validated WorkflowSpec dict.
        session_id : str
            Active session id used for signal polling and checkpointing.
        scenario : str
            Execution scenario label (stored in RunResult only).
        context : dict | None
            Initial shared context passed to every agent executor call.
            Completed step outputs accumulate here (keyed by step id).
        """
        context = context or {}
        steps: List[Dict[str, Any]] = list(spec.get("steps", []))

        run_result = RunResult(
            workflow_name=spec.get("name", "unnamed"),
            scenario=scenario,
            session_id=session_id,
            status="completed",
        )

        # Resume from checkpoint if available
        completed_ids: set = self._load_checkpoint(session_id, run_result, context)

        for step in steps:
            step_id = step.get("id", "?")

            # --- skip already-checkpointed steps ---
            if step_id in completed_ids:
                logger.debug("Step %s already completed (checkpoint), skipping.", step_id)
                continue

            # --- dependency check ---
            depends_on = step.get("depends_on", [])
            missing_deps = [d for d in depends_on if d not in completed_ids]
            if missing_deps:
                sr = StepResult(
                    step_id=step_id,
                    agent_name=step.get("agent", "?"),
                    status="skipped",
                    error=f"Unmet dependencies: {missing_deps}",
                )
                run_result.step_results.append(sr)
                logger.warning("Step %s skipped — unmet deps: %s", step_id, missing_deps)
                continue

            # --- signal poll (pre-step) ---
            should_cancel = self._handle_signals(
                session_id=session_id,
                step=step,
                context=context,
                run_result=run_result,
            )
            if should_cancel:
                run_result.status = "cancelled"
                logger.info("Workflow cancelled at step %s by user signal.", step_id)
                break

            # --- user SKIP signal applied to this step ---
            if context.get(f"_skip_{step_id}"):
                sr = StepResult(
                    step_id=step_id,
                    agent_name=step.get("agent", "?"),
                    status="skipped",
                    error="Skipped by user WorkflowSignal.",
                )
                run_result.step_results.append(sr)
                completed_ids.add(step_id)
                logger.info("Step %s skipped by user signal.", step_id)
                continue

            # --- circuit breaker check ---
            primary_agent = step.get("agent", "")
            if self._is_open(session_id, primary_agent):
                sr = StepResult(
                    step_id=step_id,
                    agent_name=primary_agent,
                    status="skipped",
                    error=f"Circuit breaker OPEN for agent '{primary_agent}'.",
                )
                run_result.step_results.append(sr)
                logger.warning(
                    "Circuit breaker open for %s; step %s skipped.",
                    primary_agent, step_id,
                )
                continue

            # --- execute with retry + fallback ---
            sr = self._execute_with_retry(
                step=step,
                session_id=session_id,
                context=context,
            )
            run_result.step_results.append(sr)

            if sr.status == "success":
                context[step_id] = sr.output
                run_result.final_outputs[step_id] = sr.output
                completed_ids.add(step_id)
                self._reset_cb(session_id, primary_agent)
                self._save_checkpoint(session_id, step_id, sr.output)
                # Persist to ContextStore if available
                if self._context_store is not None:
                    try:
                        self._context_store.set(session_id, step_id, sr.output)
                        self._context_store.append_artifact(
                            session_id=session_id,
                            artifact_type="step_output",
                            content=sr.output,
                            step_id=step_id,
                            agent_name=sr.agent_name,
                        )
                    except Exception as ctx_err:  # noqa: BLE001
                        logger.warning(
                            "Context store persistence failed for step %s: %s. "
                            "Checkpoint may be incomplete on restart.",
                            step_id, ctx_err,
                        )
            else:
                self._increment_cb(session_id, primary_agent)
                if not self.graceful_degradation:
                    run_result.status = "degraded"
                    logger.error(
                        "Step %s failed permanently; aborting workflow (graceful_degradation=False).",
                        step_id,
                    )
                    break
                else:
                    # Mark as reachable so dependents aren't blocked by
                    # dependency check, but they will receive None output
                    completed_ids.add(step_id)
                    logger.warning(
                        "Step %s failed permanently; continuing (graceful_degradation=True).",
                        step_id,
                    )

        return run_result

    # ------------------------------------------------------------------ signal handling

    def _handle_signals(
        self,
        session_id: str,
        step: Dict[str, Any],
        context: Dict[str, Any],
        run_result: RunResult,
    ) -> bool:
        """Process all pending signals.  Returns True if CANCEL received."""
        pending = self._signals.pop_pending(session_id)
        for signal in pending:
            stype = signal.type

            if stype == SignalType.CANCEL:
                logger.info("CANCEL signal received; workflow will abort.")
                return True

            elif stype == SignalType.SKIP and signal.step_id == step.get("id"):
                context[f"_skip_{step['id']}"] = True
                logger.info("SKIP signal applied to step '%s'.", step.get("id"))

            elif stype == SignalType.MODIFY and signal.step_id == step.get("id"):
                if "instruction" in signal.payload:
                    step["instruction"] = signal.payload["instruction"]
                    logger.info(
                        "MODIFY signal updated instruction for step '%s'.",
                        step.get("id"),
                    )

            elif stype == SignalType.ANNOTATE:
                note = signal.payload.get("note", "")
                run_result.final_outputs.setdefault("_annotations", []).append(
                    {"step_id": signal.step_id, "note": note}
                )
                logger.debug("ANNOTATE note added for step '%s'.", signal.step_id)

            elif stype == SignalType.PAUSE:
                # PAUSE is treated as a soft pause: log and continue
                # (non-blocking by design)
                logger.info(
                    "PAUSE signal received; pipeline continues non-blocking "
                    "(WorkflowSignal.RESUME has no effect in current implementation)."
                )

        return False

    # ------------------------------------------------------------------ retry

    def _execute_with_retry(
        self,
        step: Dict[str, Any],
        session_id: str,
        context: Dict[str, Any],
    ) -> StepResult:
        """Execute a step against its agent list with retry + back-off."""
        primary_agent = step.get("agent", "")
        instruction = step.get("instruction", "")
        candidates: List[str] = [primary_agent] + list(step.get("fallbacks", []))

        last_error: str = ""
        last_agent: str = primary_agent

        for agent_name in candidates:
            last_agent = agent_name
            for attempt in range(self.max_retries + 1):
                t0 = time.monotonic()
                try:
                    output = self._execute(agent_name, instruction, context)
                    duration_ms = (time.monotonic() - t0) * 1000
                    status = "success" if agent_name == primary_agent else "success"
                    return StepResult(
                        step_id=step["id"],
                        agent_name=agent_name,
                        status=status,
                        output=output,
                        retries=attempt,
                        duration_ms=duration_ms,
                    )
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                    duration_ms = (time.monotonic() - t0) * 1000
                    logger.warning(
                        "Step %s / agent '%s' attempt %d/%d failed: %s",
                        step["id"],
                        agent_name,
                        attempt + 1,
                        self.max_retries + 1,
                        last_error,
                    )
                    if attempt < self.max_retries:
                        sleep_s = self.backoff_base * (2 ** attempt)
                        logger.debug(
                            "Back-off %.2fs before retry (step=%s, agent=%s).",
                            sleep_s, step["id"], agent_name,
                        )
                        time.sleep(sleep_s)

        return StepResult(
            step_id=step["id"],
            agent_name=last_agent,
            status="failed",
            error=last_error,
            retries=self.max_retries,
        )

    # ------------------------------------------------------------------ circuit breaker

    def _is_open(self, session_id: str, agent_name: str) -> bool:
        return (
            self._cb_counters
            .get(session_id, {})
            .get(agent_name, 0) >= self.cb_threshold
        )

    def _increment_cb(self, session_id: str, agent_name: str) -> None:
        self._cb_counters.setdefault(session_id, {})
        self._cb_counters[session_id][agent_name] = (
            self._cb_counters[session_id].get(agent_name, 0) + 1
        )

    def _reset_cb(self, session_id: str, agent_name: str) -> None:
        self._cb_counters.get(session_id, {}).pop(agent_name, None)

    # ------------------------------------------------------------------ checkpoint

    def _load_checkpoint(
        self,
        session_id: str,
        run_result: RunResult,
        context: Dict[str, Any],
    ) -> set:
        """Load completed step ids from context_store checkpoint."""
        completed: set = set()
        if self._context_store is None:
            return completed
        try:
            checkpoint = self._context_store.get(session_id, "_checkpoint", {})
            if isinstance(checkpoint, dict):
                for step_id, output in checkpoint.items():
                    context[step_id] = output
                    run_result.final_outputs[step_id] = output
                    completed.add(step_id)
        except Exception as ckpt_err:  # noqa: BLE001
            logger.warning(
                "Failed to load checkpoint for session %s: %s. "
                "Workflow will restart from beginning.",
                session_id, ckpt_err,
            )
        return completed

    def _save_checkpoint(
        self, session_id: str, step_id: str, output: Any
    ) -> None:
        """Persist a completed step to the context_store checkpoint."""
        if self._context_store is None:
            return
        try:
            checkpoint = self._context_store.get(session_id, "_checkpoint", {}) or {}
            checkpoint[step_id] = output
            self._context_store.set(session_id, "_checkpoint", checkpoint)
        except Exception as ckpt_err:  # noqa: BLE001
            logger.warning(
                "Failed to save checkpoint for step %s in session %s: %s. "
                "Resume may re-execute this step.",
                step_id, session_id, ckpt_err,
            )


__all__ = ["RuntimeEngine", "RunResult", "StepResult"]
