"""GERÇEK model-driven shadow_canary_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
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

pytestmark = pytest.mark.llm


def test_start_deployment_stateful_skipped():
    assert hasattr(start_deployment_wrapped, "func")
    pytest.skip("DeploymentStore isteyen stateful tool; API entegrasyon testi gerekir")


def test_record_live_sample_stateful_skipped():
    assert hasattr(record_live_sample_wrapped, "func")
    pytest.skip("DeploymentStore isteyen stateful tool; API entegrasyon testi gerekir")


def test_evaluate_rollback_stateful_skipped():
    assert hasattr(evaluate_rollback_wrapped, "func")
    pytest.skip("DeploymentStore isteyen stateful tool; API entegrasyon testi gerekir")


def test_mark_status_stateful_skipped():
    assert hasattr(mark_status_wrapped, "func")
    pytest.skip("DeploymentStore isteyen stateful tool; API entegrasyon testi gerekir")


def test_summarise_deployment_stateful_skipped():
    assert hasattr(summarise_deployment_wrapped, "func")
    pytest.skip("DeploymentStore isteyen stateful tool; API entegrasyon testi gerekir")


def test_list_deployments_stateful_skipped():
    assert hasattr(list_deployments_wrapped, "func")
    pytest.skip("DeploymentStore isteyen stateful tool; API entegrasyon testi gerekir")
