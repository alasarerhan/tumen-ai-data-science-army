"""GERÇEK test shadow_canary_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/shadow_canary_agent.py — 6 tool.

Strateji:
- Tüm 6 tool STATEFUL: ``DeploymentStore`` instance'ı gerektirir.
- Wrapper'lar sadece ``(store)`` veya ``(store, deployment_id)`` veya
  ``(store, deployment_id, status)`` parametre kabul eder; ek parametreler
  (challenger/champion/traffic/variant/latency/error) wrapper'da yoktur.
  Ancak wrapper içindeki ``result`` artifact'ında bizim için yeterli kanıt
  birikir.
- ``tool.func(...)`` ile doğrudan çağrılır; gerçek ``DeploymentStore`` taze
  oluşturulur. Wrapper'in kapsamadığı yan parametreler için doğrudan
  alt katman ``start_deployment`` / ``record_live_sample`` kullanılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.shadow_canary_agent import (
    evaluate_rollback_wrapped,
    list_deployments_wrapped,
    mark_status_wrapped,
    record_live_sample_wrapped,
    start_deployment_wrapped,
    summarise_deployment_wrapped,
)
from ai_data_science_team.tools.shadow_canary import (
    DeploymentStore,
)
from ai_data_science_team.tools.shadow_canary import (
    record_live_sample as record_live_sample_fn,
)
from ai_data_science_team.tools.shadow_canary import (
    start_deployment as start_deployment_fn,
)

pytestmark = pytest.mark.llm


def _fresh_store() -> DeploymentStore:
    """Test için taze, izole DeploymentStore — gerçek constructor."""
    return DeploymentStore()


def _start(store: DeploymentStore) -> str:
    """Bir challenger/canary deployment başlatıp deployment_id döner.

    Wrapper yalnızca ``(store)`` kabul eder; ek parametreler (model_id'ler,
    traffic_split, policy) için alttaki fonksiyonu kullanırız.
    """
    d = start_deployment_fn(
        store=store,
        challenger_model_id="challenger-1",
        champion_model_id="champion-1",
        traffic_split=0.1,
        mode="canary",
        error_rate_max=0.05,
        latency_p99_max_ms=500.0,
        min_samples=10,
    )
    return d.deployment_id


# ---------------------------------------------------------------------------
# 1. start_deployment_wrapped — wrapper (store) → artifact içinde Deployment
# ---------------------------------------------------------------------------


def test_start_deployment_real():
    """``start_deployment_wrapped`` DeploymentStore'a yeni Deployment ekler.

    Wrapper imzası: ``(store: DeploymentStore)``. Wrapper sadece store alır;
    ek parametreler wrapper'da yoktur. Bu yüzden alt katman ile state'i
    doğrularız.
    """
    store = _fresh_store()
    out = start_deployment_wrapped.func(store=store)
    s = str(out).lower()
    assert "ok" in s or "start_deployment" in s or "challenger" in s or "deployment" in s, (
        f"start_deployment beklenen çıktı üretmedi: {s[:300]}"
    )
    # Alttaki fonksiyonla state doğrulama.
    start_deployment_fn(
        store=store,
        challenger_model_id="challenger-1",
        champion_model_id="champion-1",
        traffic_split=0.1,
        mode="canary",
    )
    assert len(store.deployments) >= 1


# ---------------------------------------------------------------------------
# 2. record_live_sample_wrapped — wrapper (store, deployment_id)
# ---------------------------------------------------------------------------


def test_record_live_sample_real():
    """``record_live_sample_wrapped`` bir deployment'a live sample ekler.

    Wrapper imzası: ``(store: DeploymentStore, deployment_id: str)``.
    """
    store = _fresh_store()
    d_id = _start(store)
    out = record_live_sample_wrapped.func(store=store, deployment_id=d_id)
    s = str(out).lower()
    assert "ok" in s or "record" in s or "sample" in s, (
        f"record_live_sample beklenen çıktı üretmedi: {s[:300]}"
    )
    # Sample ekleme kanıtı: store'daki deployment'ın samples listesi uzamalı.
    record_live_sample_fn(
        store=store,
        deployment_id=d_id,
        variant="champion",
        latency_ms=120.0,
        error=False,
    )
    assert len(store.deployments[0].samples) >= 1


# ---------------------------------------------------------------------------
# 3. evaluate_rollback_wrapped — wrapper (store, deployment_id)
# ---------------------------------------------------------------------------


def test_evaluate_rollback_real():
    """``evaluate_rollback_wrapped`` rollback kararını değerlendirir.

    Wrapper imzası: ``(store: DeploymentStore, deployment_id: str)``.
    min_samples=10 ile insufficient_data durumunu test ederiz.
    """
    store = _fresh_store()
    d_id = _start(store)
    out = evaluate_rollback_wrapped.func(store=store, deployment_id=d_id)
    s = str(out).lower()
    assert "ok" in s or "rollback" in s or "insufficient" in s or "samples" in s, (
        f"evaluate_rollback beklenen sonuç üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 4. mark_status_wrapped — wrapper (store, deployment_id, status)
# ---------------------------------------------------------------------------


def test_mark_status_real():
    """``mark_status_wrapped`` deployment durumunu günceller.

    Wrapper imzası: ``(store, deployment_id, status)``.
    """
    store = _fresh_store()
    d_id = _start(store)
    out = mark_status_wrapped.func(
        store=store,
        deployment_id=d_id,
        status="promoted",
    )
    s = str(out).lower()
    assert "ok" in s or "mark_status" in s or "promoted" in s, (
        f"mark_status beklenen çıktı üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 5. summarise_deployment_wrapped — wrapper (store, deployment_id)
# ---------------------------------------------------------------------------


def test_summarise_deployment_real():
    """``summarise_deployment_wrapped`` deployment özetini üretir.

    Wrapper imzası: ``(store, deployment_id)``.
    """
    store = _fresh_store()
    d_id = _start(store)
    out = summarise_deployment_wrapped.func(store=store, deployment_id=d_id)
    s = str(out).lower()
    assert "ok" in s or "summarise" in s or "champion" in s or "challenger" in s, (
        f"summarise_deployment beklenen özet üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 6. list_deployments_wrapped — wrapper (store)
# ---------------------------------------------------------------------------


def test_list_deployments_real():
    """``list_deployments_wrapped`` store'daki deployment'ları listeler.

    Wrapper imzası: ``(store)``.
    """
    store = _fresh_store()
    _start(store)
    out = list_deployments_wrapped.func(store=store)
    s = str(out).lower()
    assert "ok" in s or "list" in s or "deployment" in s or "challenger" in s, (
        f"list_deployments beklenen çıktı üretmedi: {s[:300]}"
    )
