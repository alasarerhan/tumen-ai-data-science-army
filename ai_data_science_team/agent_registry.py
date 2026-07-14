"""AgentRegistry — central catalog of all platform agents (M22).

Every agent that wants to be discoverable by the OrchestratorAgent or the
WorkflowResolver should call ``AgentRegistry.register()`` once, typically
at module import time or in ``__init__.py``.

Design
------
* **Class-level storage**: no instance needed; the registry is a singleton.
* **Metadata only**: no live agent instances are stored.  The RuntimeEngine
  instantiates agents on demand via the ``agent_class`` reference.
* **Thread-safe reads**: writes (register/clear) are protected by a lock;
  reads assume caller serialises if needed (Python GIL provides basic safety).

Usage
-----
::

    from ai_data_science_team.agent_registry import AgentRegistry
    from ai_data_science_team.agents import DataCleaningAgent

    AgentRegistry.register(
        name="DataCleaningAgent",
        agent_class=DataCleaningAgent,
        capabilities=["data_cleaning", "imputation", "type_fixing", "outlier_removal"],
        description="Cleans datasets: handles missing values, fixes dtypes, removes outliers.",
        cost_tier="low",
        tags=["data", "preprocessing"],
    )

    # Query agents that can do data_cleaning
    matches = AgentRegistry.query(capability="data_cleaning")

    # Get the full catalog (JSON serialisable)
    catalog = AgentRegistry.to_catalog()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type


# ---------------------------------------------------------------------------
# AgentMetadata
# ---------------------------------------------------------------------------


@dataclass
class AgentMetadata:
    """Metadata record for a single registered agent.

    Parameters
    ----------
    name : str
        Unique identifier used throughout the platform (e.g. ``"DataCleaningAgent"``).
    agent_class : type
        The class reference — used by RuntimeEngine to instantiate the agent.
    capabilities : list[str]
        List of capability tags (e.g. ``["data_cleaning", "imputation"]``).
    description : str
        One-line human-readable description.
    input_schema : dict
        JSON-Schema-like dict describing expected inputs.
    output_schema : dict
        JSON-Schema-like dict describing produced outputs.
    cost_tier : str
        Approximate cost level: ``"low"`` / ``"medium"`` / ``"high"``.
        Used by OrchestratorAgent to prefer cheaper alternatives.
    category : str
        Optional discovery category key used by browse/filter surfaces.
    tags : list[str]
        Arbitrary labels for grouping/filtering.
    status : str
        Optional availability/health hint for discovery surfaces.
    version : str
        Semantic version of this agent.
    """

    name: str
    agent_class: Type[Any]
    capabilities: List[str] = field(default_factory=list)
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    cost_tier: str = "medium"
    category: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "healthy"
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation (no class reference)."""
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "cost_tier": self.cost_tier,
            "tags": self.tags,
            "version": self.version,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "category": self.category,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------


# Module-level singleton state.  A class-level mutable default dict
# (`Dict = {}`) would be shared across every subclass instance and is
# notoriously easy to corrupt; using module-level state avoids that
# trap while keeping the public classmethod API intact.
_REGISTRY: Dict[str, AgentMetadata] = {}
_LOCK: threading.Lock = threading.Lock()


class AgentRegistry:
    """Class-level singleton registry for all platform agents.

    All read/write operations are exposed as class methods so callers never
    need to create an instance.  Underlying state lives at module level
    (see ``_REGISTRY`` / ``_LOCK``) to avoid class-attribute mutation
    hazards; the classmethods below delegate to those names.
    """

    # Backwards-compat class-attribute aliases (read-only intent).
    # ``cls._registry`` and ``cls._lock`` resolve to the module-level
    # singletons via these descriptors.  No per-class mutable state.
    _registry = _REGISTRY  # type: ignore[assignment]
    _lock = _LOCK  # type: ignore[assignment]

    # ------------------------------------------------------------------ write

    @classmethod
    def register(
        cls,
        name: str,
        agent_class: Type[Any],
        capabilities: Optional[List[str]] = None,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        cost_tier: str = "medium",
        category: str = "",
        tags: Optional[List[str]] = None,
        status: str = "healthy",
        version: str = "1.0.0",
        overwrite: bool = True,
    ) -> AgentMetadata:
        """Register an agent and return its metadata record.

        Parameters
        ----------
        name : str
            Unique agent name.  Existing entry is overwritten when
            *overwrite* is True (default); raises ``ValueError`` otherwise.
        agent_class : type
            The agent class (must be importable at registration time).
        capabilities : list[str]
            Capability tags for this agent.
        overwrite : bool
            If False, raises ``ValueError`` when *name* is already registered.
        """
        with cls._lock:
            if not overwrite and name in cls._registry:
                raise ValueError(
                    f"Agent '{name}' is already registered.  "
                    "Pass overwrite=True to replace it."
                )
            meta = AgentMetadata(
                name=name,
                agent_class=agent_class,
                capabilities=capabilities or [],
                description=description,
                input_schema=input_schema or {},
                output_schema=output_schema or {},
                cost_tier=cost_tier,
                category=category,
                tags=tags or [],
                status=status,
                version=version,
            )
            cls._registry[name] = meta
        return meta

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove an agent from the registry.  Silent if not found."""
        with cls._lock:
            cls._registry.pop(name, None)

    @classmethod
    def clear(cls) -> None:
        """Remove all registrations (primarily useful in tests)."""
        with cls._lock:
            cls._registry.clear()

    # ------------------------------------------------------------------ read

    @classmethod
    def get(cls, name: str) -> AgentMetadata:
        """Return the metadata record for *name*.

        Raises
        ------
        KeyError
            If *name* is not registered.
        """
        with cls._lock:
            if name not in cls._registry:
                raise KeyError(
                    f"Agent '{name}' is not registered.  "
                    f"Available: {sorted(cls._registry.keys())}"
                )
            return cls._registry[name]

    @classmethod
    def get_or_none(cls, name: str) -> Optional[AgentMetadata]:
        """Return the metadata record or *None* if not registered."""
        with cls._lock:
            return cls._registry.get(name)

    @classmethod
    def query(
        cls,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
        cost_tier: Optional[str] = None,
    ) -> List[AgentMetadata]:
        """Return agents matching all supplied filters (AND semantics).

        Parameters
        ----------
        capability : str | None
            Filter to agents whose ``capabilities`` list contains this value.
        tag : str | None
            Filter to agents whose ``tags`` list contains this value.
        cost_tier : str | None
            Filter by cost tier (``"low"`` / ``"medium"`` / ``"high"``).
        """
        with cls._lock:
            results = list(cls._registry.values())

        if capability:
            results = [m for m in results if capability in m.capabilities]
        if tag:
            results = [m for m in results if tag in m.tags]
        if cost_tier:
            results = [m for m in results if m.cost_tier == cost_tier]

        return sorted(results, key=lambda m: m.name)

    @classmethod
    def list_all(cls) -> List[AgentMetadata]:
        """Return all registered agents sorted by name."""
        with cls._lock:
            return sorted(cls._registry.values(), key=lambda m: m.name)

    @classmethod
    def names(cls) -> List[str]:
        """Return a sorted list of all registered agent names."""
        with cls._lock:
            return sorted(cls._registry.keys())

    @classmethod
    def size(cls) -> int:
        """Return the number of registered agents."""
        with cls._lock:
            return len(cls._registry)

    @classmethod
    def to_catalog(cls) -> List[Dict[str, Any]]:
        """Return a JSON-serialisable list of all agent metadata dicts."""
        return [m.to_dict() for m in cls.list_all()]


__all__ = ["AgentMetadata", "AgentRegistry"]
