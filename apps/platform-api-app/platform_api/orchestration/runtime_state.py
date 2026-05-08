from __future__ import annotations

from functools import lru_cache

from ai_data_science_team.redis_stores import RedisContextStore, RedisSignalStore

from platform_api.core.config import settings
from platform_api.core.service_errors import ValidationError


def validate_runtime_state_settings(*, raise_runtime: bool = False) -> None:
    mode = settings.orchestration_execution_mode.strip().lower()
    if mode != "staged_m22":
        return

    redis_url = settings.orchestration_state_redis_url.strip()
    if not redis_url:
        message = (
            "orchestration_state_redis_url must be set when orchestration_execution_mode=staged_m22."
        )
        if raise_runtime:
            raise RuntimeError(message)
        raise ValidationError(message)


@lru_cache(maxsize=1)
def get_orchestration_context_store() -> RedisContextStore:
    validate_runtime_state_settings()
    return RedisContextStore(
        redis_url=settings.orchestration_state_redis_url.strip(),
        require_redis=True,
    )


@lru_cache(maxsize=1)
def get_orchestration_signal_store() -> RedisSignalStore:
    validate_runtime_state_settings()
    return RedisSignalStore(
        redis_url=settings.orchestration_state_redis_url.strip(),
        require_redis=True,
    )


def reset_runtime_state_caches() -> None:
    get_orchestration_context_store.cache_clear()
    get_orchestration_signal_store.cache_clear()
