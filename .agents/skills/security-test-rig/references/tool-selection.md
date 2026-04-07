# Tool Selection

## Common Tools
- `semgrep`: broad static security pattern matching across stacks
- `gitleaks`: secret and token discovery in repository history and files

## Python
- `bandit`: Python-focused secure coding checks
- `pip-audit`: dependency vulnerability review for installed packages

## Java / Spring
- `owasp dependency-check`: dependency vulnerability analysis for Maven or Gradle builds
- `spotbugs`: static analysis with Java-oriented bug patterns

## .NET / ASP.NET Core
- `dotnet list package --vulnerable --include-transitive`: dependency vulnerability visibility
- `semgrep`: supplemental static pattern review for application code

## Node / TypeScript
- `npm audit --omit=dev`: dependency vulnerability visibility for production packages
- `semgrep scan .`: supplemental static pattern review for application code

## Selection Rules
- Start with the lowest-friction common tools when the stack is unclear.
- Prefer native ecosystem tooling for dependency visibility.
- Never imply a tool was run if the user only asked for a plan.
