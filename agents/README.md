# Legacy Agents — DEPRECATED

This directory contains the **original agent implementations** from the first generation of the platform.

## Status: DEPRECATED ✅ Still functional, not deleted

These agents still work and can be imported and used. However, all new development should target the **modernized agent package** at `ai_data_science_team/ai_data_science_team/agents/`.

## Why keep them?

- `H2OMLAgent`, `EDAToolsAgent`, `MLflowToolsAgent` etc. are actively used by existing tests and pipelines
- They use different ML frameworks (H2O) and code-generation patterns that the modern spec agents don't fully replicate
- Removing them would break the `agents/` namespace package that `__init__.py` relies on

## Modern equivalents

| Legacy agent | Modern equivalent | Notes |
|---|---|---|
| `DataCleaningAgent` | — | Unique code-generation pattern, no direct spec replacement |
| `DataLoaderToolsAgent` | — | Still the primary file-loading agent |
| `DataWranglingAgent` | — | Unique code-generation pattern |
| `FeatureEngineeringAgent` | — | Unique code-generation pattern |
| `DataVisualizationAgent` | — | Unique code-generation pattern |
| `SQLDatabaseAgent` | — | Still the primary SQL agent |
| `EDAToolsAgent` | `DataQualityAgent`, `B1Agent` | Modern split into profiling + quality |
| `H2OMLAgent` | `E1Agent` (removed) → use sklearn tools directly | H2O-specific, no direct replacement |
| `MLflowToolsAgent` | `J4Agent` (removed) → use MLflow SDK | Thin wrapper around mlflow SDK |

## Migration path

1. New code should import from `ai_data_science_team.agents` (the namespace package resolves to the modern package first)
2. Legacy code continues to work unchanged
3. When all consumers have migrated, this directory can be archived
