from platform_api.services.workflow_chain_validator import canonicalize_agent, inspect_workflow_spec


def test_canonicalize_agent_supports_aliases():
    assert canonicalize_agent("Data Cleaner") == "DataCleaningAgent"
    assert canonicalize_agent("Narrative Synthesizer") == "NarrativeAgent"
    assert canonicalize_agent("data_clean") == "DataCleaningAgent"


def test_inspect_workflow_spec_warns_for_advisory_chain():
    result = inspect_workflow_spec(
        {
            "name": "Advisory flow",
            "graph": {
                "nodes": [
                    {"id": "n1", "label": "EDA", "agent": "EDAToolsAgent"},
                    {"id": "n2", "label": "Data Cleaning", "agent": "DataCleaningAgent"},
                ],
                "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
            },
        }
    )

    assert result["errors"] == []
    assert any(warning["code"] == "conditional_edge" for warning in result["warnings"])


def test_inspect_workflow_spec_warns_for_missing_model_inputs():
    result = inspect_workflow_spec(
        {
            "name": "Monitoring flow",
            "graph": {
                "nodes": [
                    {"id": "n1", "label": "Model Monitoring", "agent": "ModelMonitoringAgent"},
                ],
                "edges": [],
            },
        }
    )

    assert result["errors"] == []
    assert any(warning["code"] == "insufficient_inputs" for warning in result["warnings"])
