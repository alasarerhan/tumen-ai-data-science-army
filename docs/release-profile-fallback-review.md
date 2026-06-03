# Release Profile Fallback Review

Status: completed for current open release-safety task.

Last updated: 2026-06-03.

## Reviewed Surfaces

| Surface | Current behavior | Release safety decision | Evidence |
|---|---|---|---|
| Run orchestration creation | Local run id fallback only when `DEPLOYMENT_PROFILE=local` and `ALLOW_LOCAL_RUN_FALLBACK=true` | Safe; release raises validation/upstream errors instead of hiding orchestration failure | `tests/test_run_orchestration_service.py` |
| `staged_m22` runtime mode | Allowed only in local or staging profile | Safe until lifecycle parity is proven | `tests/test_run_orchestration_service.py` |
| Run log stream | Prefect logs are preferred; mock stream was previously available after provider failure | Fixed; mock logs are now local-only and release returns `503` when provider logs are unavailable | `tests/test_logs_release_fallback.py` |
| Chat fallback reply path | ChatWorkspace dependency/runtime fallback still returns deterministic assistant content | Accepted for design-partner scope; should be revisited before GA if release profile must require live graph execution | Existing chat service tests |
| Discovery fallback search | Uses curated/registry fallback when vector search is unavailable | Accepted; discovery remains a UX/search fallback, not a production execution substitute | `tests/test_agent_discovery.py` |

## Code Change

- `platform_api/routes/logs.py` no longer returns mock logs in release profile.
- Local mock log stream remains available only when `DEPLOYMENT_PROFILE=local`
  and `ALLOW_LOCAL_RUN_FALLBACK=true`.

## Commands

```powershell
cd apps/platform-api-app
python -m pytest tests/test_run_orchestration_service.py tests/test_logs_release_fallback.py -q
```

Result: 12 passed.

## Residual Risk

- Chat fallback is still intentionally product-friendly. Before GA, decide
  whether release profile should fail closed for ChatWorkspace dependency
  failures or continue returning deterministic fallback guidance.
