$ErrorActionPreference = "Stop"

function Write-TextFile {
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
}

$root = (Resolve-Path ".").Path
$skillsRoot = Join-Path $root ".claude/skills"
$today = Get-Date -Format "yyyy-MM-dd"
$generatedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"

$skills = @(
    @{ id = "project-architecture"; title = "Project Architecture"; description = "Module boundaries and ownership across frontend + platform API."; focus = "Prevent architecture drift while closing M10/M12/M17-UI/M19/M20." },
    @{ id = "python-backend-standards"; title = "Python Backend Standards"; description = "Typed, testable backend patterns for FastAPI services."; focus = "Keep routes thin and business logic in services." },
    @{ id = "typescript-frontend-standards"; title = "TypeScript Frontend Standards"; description = "Strict DTO typing and resilient UI state handling."; focus = "Stabilize login/dashboard/workflow path with consistent async states." },
    @{ id = "fastapi-api-design"; title = "FastAPI API Design"; description = "Stable REST and SSE contracts for chat/workflow/run domains."; focus = "Avoid breaking API consumers while adding new endpoints." },
    @{ id = "workflow-designer-engineering"; title = "Workflow Designer Engineering"; description = "React Flow + Monaco + schedule quality rules."; focus = "Guarantee graph <-> YAML round-trip fidelity." },
    @{ id = "chat-sse-realtime"; title = "Chat SSE Realtime"; description = "Chat session/message/upload lifecycle and stream behavior."; focus = "Make M21 chat experience production-safe." },
    @{ id = "signal-monitoring-ui"; title = "Signal Monitoring UI"; description = "Run timeline, signal stream, and intervention consistency."; focus = "Deliver M17-UI with auditable intervention signals." },
    @{ id = "chart-artifact-contract"; title = "Chart Artifact Contract"; description = "Single ECharts payload contract for Sankey/Network/Trend."; focus = "Keep artifact rendering consistent between report and workspace." },
    @{ id = "database-migrations"; title = "Database Migrations"; description = "Safe schema changes for SQLite/Postgres compatibility."; focus = "Avoid runtime errors from DB-specific defaults/functions." },
    @{ id = "testing-quality-gates"; title = "Testing Quality Gates"; description = "Enforce TG1/TG2/TG3 evidence at milestone closure."; focus = "No 'done' status without tests and regression coverage." },
    @{ id = "security-authz-secrets"; title = "Security AuthZ and Secrets"; description = "Tenant isolation, role checks, and secret hygiene."; focus = "Protect multi-tenant boundaries and avoid secret leakage." },
    @{ id = "observability-slo"; title = "Observability and SLO"; description = "Structured logs, metrics, tracing, and alert readiness."; focus = "Keep incident triage fast with strong telemetry." },
    @{ id = "performance-budgeting"; title = "Performance Budgeting"; description = "Latency and payload discipline on critical user journeys."; focus = "Protect golden-path responsiveness under new features." },
    @{ id = "documentation-release-readiness"; title = "Documentation and Release Readiness"; description = "Docs, rollback notes, release evidence discipline."; focus = "Support M15 docs and M20 GA closure quality." },
    @{ id = "devops-deployment-reliability"; title = "DevOps Deployment Reliability"; description = "Deterministic deploy/rollback standards across environments."; focus = "Keep releases reproducible and reversible." },
    @{ id = "dependency-version-governance"; title = "Dependency Version Governance"; description = "Controlled dependency updates with explicit version ledger."; focus = "Reduce break risk from uncontrolled upgrades." },
    @{ id = "accessibility-ux-quality"; title = "Accessibility and UX Quality"; description = "Core UX clarity and accessibility requirements."; focus = "Maintain customer trust in first 15-minute experience." },
    @{ id = "data-modeling-contracts"; title = "Data Modeling Contracts"; description = "DTO/model boundaries and payload compatibility rules."; focus = "Keep frontend/backend contracts synchronized." },
    @{ id = "error-handling-resilience"; title = "Error Handling and Resilience"; description = "Predictable failures, retries, and recovery paths."; focus = "Prevent silent failures in chat/workflow/monitor flows." },
    @{ id = "product-golden-path"; title = "Product Golden Path"; description = "PO-level prioritization and quality guardrails for core flow."; focus = "Prioritize trust and clarity over secondary capability expansion." },
    @{ id = "project-manager"; title = "Project Manager"; description = "Cross-skill compliance and gate enforcement controller."; focus = "Block completion claims without code+test+docs+rollback evidence." }
)

New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

$index = @("# Skills Index", "", "Generated: $generatedAt", "")

foreach ($skill in $skills) {
    $skillDir = Join-Path $skillsRoot $skill.id
    $refDir = Join-Path $skillDir "references"
    New-Item -ItemType Directory -Path $refDir -Force | Out-Null

    $skillMd = @"
---
name: $($skill.id)
description: $($skill.description)
owner: platform-team
last_verified: $today
---

# $($skill.title)

## Purpose
$($skill.focus)

## Trigger
- Use when this domain is touched by implementation or refactor.
- Use before claiming milestone completion in this domain.

## Required Rules
- Keep changes within clear module ownership boundaries.
- Preserve backward compatibility or document break strategy.
- Add tests for success and failure paths.
- Update docs and rollback notes for behavior-changing work.

## Acceptance Gates
- TG1/TG2/TG3 evidence exists for touched scope.
- Contract changes are reflected in DTO/schema definitions.
- Known risks and assumptions are explicitly documented.

## Output Contract
- Updated code.
- Tests.
- Documentation notes.
- Rollback guidance.

## References
- references/patterns.md
- references/anti-patterns.md
- references/checklist.md
"@

    $patterns = @"
# Patterns - $($skill.title)

- Prefer explicit contracts and typed interfaces.
- Keep responsibilities separated (route/service/model/ui).
- Use deterministic, testable behavior for critical flows.
"@

    $antiPatterns = @"
# Anti-Patterns - $($skill.title)

- Hidden breaking changes in public interfaces.
- Logic duplication across modules.
- Incomplete work marked as done without evidence.
"@

    $checklist = @"
# Checklist - $($skill.title)

- [ ] Scope and ownership are clear.
- [ ] Tests include happy and failure paths.
- [ ] Docs reflect behavior changes.
- [ ] Rollback path is documented.
"@

    Write-TextFile -Path (Join-Path $skillDir "SKILL.md") -Content $skillMd
    Write-TextFile -Path (Join-Path $refDir "patterns.md") -Content $patterns
    Write-TextFile -Path (Join-Path $refDir "anti-patterns.md") -Content $antiPatterns
    Write-TextFile -Path (Join-Path $refDir "checklist.md") -Content $checklist

    $index += "- $($skill.id) - $($skill.description)"
}

$manifest = @{
    generated_at = $generatedAt
    generator = "tools/bootstrap_claude_skills.ps1"
    project_root = $root
    skill_count = $skills.Count
    skills = ($skills | ForEach-Object {
            @{
                id = $_.id
                title = $_.title
                description = $_.description
                path = ".claude/skills/$($_.id)/SKILL.md"
            }
        })
}

Write-TextFile -Path (Join-Path $skillsRoot "_bootstrap-manifest.json") -Content ($manifest | ConvertTo-Json -Depth 6)

$versionLedger = @"
# Version Verification Ledger

Date: 2026-03-23

## Frontend
- react 19.2.4
- vite 8.0.2
- typescript 5.9.3
- react-router 7.13.1
- @tanstack/react-query 5.95.0
- vitest 4.1.0
- echarts 6.0.0
- @monaco-editor/react 4.7.0
- reactflow 11.11.4

## Backend
- fastapi 0.135.1
- uvicorn 0.42.0
- sqlalchemy 2.0.48
- alembic 1.18.4
- pydantic-settings 2.13.1
- prefect 3.6.23
- psycopg 3.3.3
- openai 2.29.0

## Runtime
- node v24.11.1
- python 3.13.5
"@

Write-TextFile -Path (Join-Path $skillsRoot "VERSION_VERIFICATION.md") -Content $versionLedger
Write-TextFile -Path (Join-Path $skillsRoot "README.md") -Content ($index -join "`r`n")

Write-Output "SKILLS_ROOT=$skillsRoot"
Write-Output "SKILL_COUNT=$($skills.Count)"
