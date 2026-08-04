from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from ai_data_science_team.runtime_engine import RuntimeEngine
from ai_data_science_team.signals import SignalType


class _MemoryContextStore:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, Any]] = {}
        self.artifacts: list[dict[str, Any]] = []

    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        return self.values.get(session_id, {}).get(key, default)

    def set(self, session_id: str, key: str, value: Any) -> None:
        self.values.setdefault(session_id, {})[key] = value

    def append_artifact(
        self,
        *,
        session_id: str,
        artifact_type: str,
        content: Any,
        step_id: str,
        agent_name: str,
    ) -> None:
        self.artifacts.append(
            {
                "session_id": session_id,
                "artifact_type": artifact_type,
                "content_type": type(content).__name__,
                "step_id": step_id,
                "agent_name": agent_name,
            }
        )


class _NoopSignalStore:
    def pop_pending(self, session_id: str) -> list[Any]:
        return []


class _CancelSignalStore:
    def __init__(self) -> None:
        self._emitted = False

    def pop_pending(self, session_id: str) -> list[Any]:
        if self._emitted:
            return []
        self._emitted = True
        return [SimpleNamespace(type=SignalType.CANCEL, step_id=None, payload={})]


def build_runtime_engine_parity_report() -> dict[str, Any]:
    session_id = f"runtime-parity-{uuid4().hex[:12]}"
    attempts: dict[str, int] = {}
    context_store = _MemoryContextStore()

    def _executor(agent_name: str, instruction: str, context: dict[str, Any]) -> dict[str, Any]:
        attempts[agent_name] = attempts.get(agent_name, 0) + 1
        if agent_name == "RetryAgent" and attempts[agent_name] == 1:
            raise RuntimeError("intentional retry probe")
        return {
            "agent": agent_name,
            "instruction_key": instruction.split(" ", maxsplit=1)[0] if instruction else "none",
            "artifact": {
                "artifact_type": "model" if agent_name == "RetryAgent" else "profile_report",
                "safe_payload_keys": sorted(context.keys()),
            },
        }

    spec = {
        "name": "runtime-engine-platform-parity",
        "steps": [
            {"id": "profile", "agent": "ProfileAgent", "instruction": "profile dataset"},
            {
                "id": "train",
                "agent": "RetryAgent",
                "instruction": "train model",
                "depends_on": ["profile"],
            },
        ],
    }
    engine = RuntimeEngine(
        agent_executor=_executor,
        signal_store=_NoopSignalStore(),
        context_store=context_store,
        max_retries=1,
        backoff_base=0,
        graceful_degradation=False,
    )
    run_result = engine.run(spec=spec, session_id=session_id, scenario="supervised", context={})

    cancel_session_id = f"{session_id}-cancel"
    cancel_engine = RuntimeEngine(
        agent_executor=lambda _agent, _instruction, _context: {},
        signal_store=_CancelSignalStore(),
        context_store=_MemoryContextStore(),
        max_retries=0,
        backoff_base=0,
        graceful_degradation=False,
    )
    cancel_result = cancel_engine.run(
        spec=spec, session_id=cancel_session_id, scenario="supervised", context={}
    )

    step_logs = [
        {
            "level": "INFO" if step.status == "success" else "ERROR",
            "target_step": step.step_id,
            "message": f"RuntimeEngine step {step.step_id} finished with status {step.status}.",
        }
        for step in run_result.step_results
    ]
    signal_events = [
        {
            "signal_type": "node_succeeded" if step.status == "success" else "node_failed",
            "target_step": step.step_id,
            "payload": {"agent_name": step.agent_name, "retries": step.retries},
        }
        for step in run_result.step_results
    ]
    retry_steps = [step for step in run_result.step_results if step.retries > 0]

    surface_mapping = {
        "logs": {
            "status": "mapped",
            "target_contract": "/v1/runs/{id}/logs",
            "records": step_logs,
        },
        "signals": {
            "status": "mapped",
            "target_contract": "/v1/runs/{id}/signals",
            "records": signal_events,
        },
        "artifacts": {
            "status": "mapped",
            "target_contract": "/v1/artifacts",
            "records": context_store.artifacts,
        },
        "retry": {
            "status": "mapped",
            "target_contract": "/v1/runs/{id}/nodes/{node_id}/retry",
            "covered": bool(retry_steps),
            "records": [{"step_id": step.step_id, "retries": step.retries} for step in retry_steps],
        },
        "cancel": {
            "status": "mapped",
            "target_contract": "/v1/runs/{id}/cancel and workflow signals",
            "covered": cancel_result.status == "cancelled",
            "records": [{"session_id": cancel_session_id, "status": cancel_result.status}],
        },
        "scheduler": {
            "status": "not_runtime_replacement",
            "target_contract": "Prefect/scheduler remains canonical for schedules",
            "covered": True,
            "records": [
                {"decision": "RuntimeEngine parity harness does not promote scheduler behavior"}
            ],
        },
    }
    checks = {
        "runtime_completed": run_result.status == "completed",
        "logs_mapped": len(step_logs) == len(run_result.step_results),
        "signals_mapped": len(signal_events) == len(run_result.step_results),
        "artifacts_mapped": len(context_store.artifacts) >= len(run_result.step_results),
        "retry_mapped": bool(retry_steps),
        "cancel_mapped": cancel_result.status == "cancelled",
        "scheduler_non_replacement_recorded": surface_mapping["scheduler"]["covered"] is True,
    }
    status = "passed" if all(checks.values()) else "failed"
    return {
        "status": status,
        "execution_mode": "staged_m22_parity_harness",
        "promotion_decision": "do_not_promote_default_until_reviewed",
        "session_id": session_id,
        "runtime_result": run_result.to_dict(),
        "cancel_result": cancel_result.to_dict(),
        "surface_mapping": surface_mapping,
        "checks": checks,
    }
