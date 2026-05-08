# Created a contributing.md file 

# Contributing to AI Data Science Team

Thank you for your interest in contributing to the AI Data Science Team project! We welcome contributions from the community to help make this project better.

## Getting Started

To get started with contributing, follow these steps:

1.  **Fork the repository**: Click the "Fork" button on the top right corner of the repository page to create a copy of the repository in your GitHub account.
2.  **Clone the repository**: Clone your forked repository to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/ai-data-science-team.git
    cd ai-data-science-team
    ```
3.  **Set up the environment**:
    It is recommended to use a virtual environment.
    ```bash
    # Create a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

    Install the package in editable mode with dependencies:
    ```bash
    pip install -e .
    ```

## Running the App

To run the AI Pipeline Studio app locally:

```bash
streamlit run apps/ai-pipeline-studio-app/app.py
```

## Reporting Bugs

If you find a bug, please open an issue in the issue tracker. Include as much detail as possible, such as:
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Screenshots (if applicable)
- Your environment details (OS, Python version, etc.)

## Submitting Pull Requests

1.  **Create a branch**: Create a new branch for your feature or bug fix.
    ```bash
    git checkout -b feature/your-feature-name
    ```
2.  **Make changes**: Make your changes to the code.
3.  **Test your changes**: Ensure that your changes work as expected and do not break existing functionality.
4.  **Commit your changes**: Commit your changes with a descriptive commit message.
    ```bash
    git commit -m "Description of your changes"
    ```
5.  **Push to GitHub**: Push your changes to your forked repository.
    ```bash
    git push origin feature/your-feature-name
    ```
6.  **Create a Pull Request**: Go to the original repository and click "Compare & pull request" to submit your changes for review.

We appreciate your contributions!

---

## Agent Development Guidelines

> **Important:** All new agents **must** be built on top of the `BaseAgent` base class.

### Using `BaseAgent`

`BaseAgent` (defined in `ai_data_science_team/templates/agent_templates.py`) is a subclass of LangGraph's `CompiledStateGraph`.  It provides:

- Unified parameter management (`_params`, `update_params()`)
- Automatic graph rebuilding on parameter changes
- Consistent `invoke()` / `ainvoke()` / `stream()` interface
- Duplicate-message deduplication in responses

### Minimal Agent Template

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import create_react_agent

from ai_data_science_team.templates.agent_templates import BaseAgent


# 1. Define tools
@tool
def my_tool(x: int) -> int:
    """Doubles x."""
    return x * 2

_MY_TOOLS = [my_tool]


# 2. Subclass BaseAgent
class MyAgent(BaseAgent):
    """A minimal example agent."""

    def __init__(self, model: BaseChatModel, **kwargs):
        super().__init__(model=model, **kwargs)

    def _make_compiled_graph(self):
        model = self._params["model"]
        system_prompt = "You are a helpful assistant."
        return create_react_agent(
            model=model,
            tools=_MY_TOOLS,
            prompt=system_prompt,
        )

    def invoke_agent(self, user_instructions: str, **kwargs):
        """Convenience wrapper with a standard input schema."""
        return self.invoke(
            input={"messages": [("human", user_instructions)]},
            **kwargs,
        )
```

### Key Rules

1. **Always call `super().__init__(**params)`** so parameter storage and graph wiring work correctly.
2. **Implement `_make_compiled_graph()`** — this is the only required override.  It must return a compiled LangGraph (`CompiledStateGraph`).
3. **Re-use `_params`** inside `_make_compiled_graph()` so `update_params()` correctly triggers a graph rebuild.
4. **Tools** should be decorated with `@tool` (and `response_format="content_and_artifact"` for tools that return complex artefacts).
5. **Tests** should instantiate the agent with a `FakeChatModel` (no real API keys needed) to verify class structure and `update_params()` behaviour.

### File Locations

| Artefact | Directory |
|---|---|
| Tools | `ai_data_science_team/tools/<domain>.py` |
| Agents | `ai_data_science_team/ml_agents/<name>_agent.py` |
| Tests | `tests/test_<domain>.py` |
| Export | Add to `ml_agents/__init__.py` |
