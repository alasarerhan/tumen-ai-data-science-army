# sc-rce Results

## Finding: RCE-001
- Severity: Critical
- Confidence: 95
- CWE: CWE-94 (Code Injection), CWE-78 (OS Command Injection)
- Title: Unsandboxed dynamic `exec` path allows capability escape via whitelisted module objects
- Evidence:
- `ai_data_science_team/templates/agent_templates.py:919-933` executes generated code with `exec(...)` and then executes generated function against live SQL connection.
- `ai_data_science_team/templates/agent_templates.py:914-917` exposes `pd` and `sql` in globals.
- `ai_data_science_team/templates/agent_templates.py:46-83` uses pattern-based safety checks that do not prevent attribute-chain escapes.
- Reachability:
- `ai_data_science_team/agents/sql_database_agent.py:827-838` calls `node_func_execute_agent_from_sql_connection(...)` during agent execution.
- Verified behavior (local PoC): crafted function accessed filesystem via `pd.io.common.os` and returned current working directory and directory listing.
- Impact: Arbitrary code/data access in process context, with access to DB connection object and host filesystem.
- Remediation:
- Remove in-process `exec` path for untrusted/generated code.
- Execute generated SQL/data code in isolated subprocess/container with strict seccomp/apparmor and read-only mounts.
- Do not expose high-capability modules (`pd`, `sql`) directly to untrusted code; pass pre-validated query primitives instead.
