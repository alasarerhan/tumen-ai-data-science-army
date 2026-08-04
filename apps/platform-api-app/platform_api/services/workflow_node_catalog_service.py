from __future__ import annotations

from copy import deepcopy

ArtifactType = str


_CATALOG: list[dict] = [
    {
        "type": "manual.trigger",
        "label": "Manual Trigger",
        "category": "Triggers",
        "description": "Starts a workflow from a user-initiated test or production run.",
        "inputs": [],
        "outputs": [{"name": "input_dataset", "artifact_type": "dataset", "required": False}],
        "ui": {"icon": "play", "color": "blue", "config": []},
        "timeout_seconds": 30,
        "retry_policy": {"max_attempts": 0, "backoff_seconds": 0},
        "resources": {"class": "control"},
    },
    {
        "type": "schedule.trigger",
        "label": "Schedule Trigger",
        "category": "Triggers",
        "description": "Starts a workflow on a cron schedule.",
        "inputs": [],
        "outputs": [
            {"name": "scheduled_context", "artifact_type": "trigger_context", "required": False}
        ],
        "ui": {
            "icon": "calendar-clock",
            "color": "blue",
            "config": [{"key": "cron", "type": "string", "required": True}],
        },
        "timeout_seconds": 30,
        "retry_policy": {"max_attempts": 0, "backoff_seconds": 0},
        "resources": {"class": "control"},
    },
    {
        "type": "webhook.trigger",
        "label": "Webhook Trigger",
        "category": "Triggers",
        "description": "Starts a workflow from an inbound webhook payload.",
        "inputs": [],
        "outputs": [{"name": "payload", "artifact_type": "trigger_context", "required": True}],
        "ui": {
            "icon": "webhook",
            "color": "blue",
            "config": [{"key": "secret_ref", "type": "credential", "required": False}],
        },
        "timeout_seconds": 30,
        "retry_policy": {"max_attempts": 0, "backoff_seconds": 0},
        "resources": {"class": "control"},
    },
    {
        "type": "dataset.profile",
        "label": "Dataset Profile",
        "category": "Profiling",
        "description": "Profiles schema, missingness, distributions, leakage hints, and data quality risks.",
        "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": True}],
        "outputs": [{"name": "profile", "artifact_type": "profile_report", "required": True}],
        "ui": {
            "icon": "table-properties",
            "color": "cyan",
            "config": [{"key": "sample_rows", "type": "number", "required": False}],
        },
        "timeout_seconds": 600,
        "retry_policy": {"max_attempts": 2, "backoff_seconds": 10},
        "resources": {"class": "cpu_medium"},
    },
    {
        "type": "data.clean",
        "label": "Clean Data",
        "category": "Cleaning",
        "description": "Applies validated missing-value, outlier, type, and duplicate handling steps.",
        "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": True}],
        "outputs": [{"name": "clean_dataset", "artifact_type": "dataset", "required": True}],
        "ui": {
            "icon": "sparkles",
            "color": "emerald",
            "config": [
                {
                    "key": "strategy",
                    "type": "select",
                    "options": ["auto", "conservative", "aggressive"],
                    "required": True,
                }
            ],
        },
        "timeout_seconds": 1200,
        "retry_policy": {"max_attempts": 2, "backoff_seconds": 20},
        "resources": {"class": "cpu_medium"},
    },
    {
        "type": "feature.engineer",
        "label": "Feature Engineer",
        "category": "Feature Engineering",
        "description": "Creates and validates model-ready features from cleaned datasets.",
        "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": True}],
        "outputs": [{"name": "feature_set", "artifact_type": "feature_set", "required": True}],
        "ui": {
            "icon": "git-branch",
            "color": "violet",
            "config": [{"key": "target_column", "type": "string", "required": False}],
        },
        "timeout_seconds": 1800,
        "retry_policy": {"max_attempts": 1, "backoff_seconds": 30},
        "resources": {"class": "cpu_large"},
    },
    {
        "type": "model.train",
        "label": "Train Model",
        "category": "Modeling",
        "description": "Trains candidate models and records parameters, metrics, and model artifact references.",
        "inputs": [{"name": "features", "artifact_type": "feature_set", "required": True}],
        "outputs": [
            {"name": "model", "artifact_type": "model", "required": True},
            {"name": "metrics", "artifact_type": "metrics", "required": True},
        ],
        "ui": {
            "icon": "brain-circuit",
            "color": "purple",
            "config": [
                {
                    "key": "task_type",
                    "type": "select",
                    "options": ["classification", "regression", "forecasting"],
                    "required": True,
                }
            ],
        },
        "timeout_seconds": 3600,
        "retry_policy": {"max_attempts": 1, "backoff_seconds": 60},
        "resources": {"class": "cpu_large"},
    },
    {
        "type": "model.evaluate",
        "label": "Evaluate Model",
        "category": "Evaluation",
        "description": "Evaluates model quality, bias, drift readiness, and promotion thresholds.",
        "inputs": [
            {"name": "model", "artifact_type": "model", "required": True},
            {"name": "dataset", "artifact_type": "dataset", "required": False},
        ],
        "outputs": [{"name": "evaluation", "artifact_type": "evaluation_report", "required": True}],
        "ui": {
            "icon": "line-chart",
            "color": "amber",
            "config": [{"key": "metric", "type": "string", "required": False}],
        },
        "timeout_seconds": 1200,
        "retry_policy": {"max_attempts": 1, "backoff_seconds": 30},
        "resources": {"class": "cpu_medium"},
    },
    {
        "type": "report.generate",
        "label": "Generate Report",
        "category": "Reports",
        "description": "Generates an analyst-ready report with methods, findings, caveats, and next actions.",
        "inputs": [
            {"name": "profile", "artifact_type": "profile_report", "required": False},
            {"name": "evaluation", "artifact_type": "evaluation_report", "required": False},
        ],
        "outputs": [{"name": "report", "artifact_type": "report", "required": True}],
        "ui": {
            "icon": "file-text",
            "color": "pink",
            "config": [
                {
                    "key": "audience",
                    "type": "select",
                    "options": ["technical", "business", "executive"],
                    "required": True,
                }
            ],
        },
        "timeout_seconds": 900,
        "retry_policy": {"max_attempts": 2, "backoff_seconds": 15},
        "resources": {"class": "llm"},
    },
    {
        "type": "approval.wait",
        "label": "Approval",
        "category": "HITL",
        "description": "Pauses execution until a human approves, rejects, or requests changes.",
        "inputs": [{"name": "review_payload", "artifact_type": "any", "required": True}],
        "outputs": [{"name": "approval", "artifact_type": "approval_decision", "required": True}],
        "ui": {
            "icon": "user-check",
            "color": "orange",
            "config": [{"key": "approver_role", "type": "string", "required": True}],
        },
        "timeout_seconds": 604800,
        "retry_policy": {"max_attempts": 0, "backoff_seconds": 0},
        "resources": {"class": "control"},
    },
    {
        "type": "artifact.export",
        "label": "Export Artifact",
        "category": "Artifacts",
        "description": "Exports datasets, reports, metrics, models, or lineage bundles to configured storage.",
        "inputs": [{"name": "artifact", "artifact_type": "any", "required": True}],
        "outputs": [{"name": "export", "artifact_type": "export_manifest", "required": True}],
        "ui": {
            "icon": "archive",
            "color": "slate",
            "config": [
                {
                    "key": "format",
                    "type": "select",
                    "options": ["csv", "parquet", "html", "json", "model_bundle"],
                    "required": True,
                }
            ],
        },
        "timeout_seconds": 600,
        "retry_policy": {"max_attempts": 3, "backoff_seconds": 20},
        "resources": {"class": "io"},
    },
]


def get_workflow_node_catalog() -> list[dict]:
    return deepcopy(_CATALOG)


def get_workflow_node_catalog_by_type() -> dict[str, dict]:
    return {node["type"]: node for node in get_workflow_node_catalog()}


def list_supported_node_types() -> set[str]:
    return {node["type"] for node in _CATALOG}
