"""Agent discovery service with Pinecone integration.

This module provides multi-surface agent discovery:
- Search: Natural language search via Pinecone vector similarity
- Browse: Category-based browsing
- Recommendation: Workflow-based agent recommendations

Best Practices Reference:
https://www.gramercystudios.com/thinking/multi-surface-discoverability
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ai_data_science_team.agent_registry import AgentRegistry

from platform_api.core.config import settings
from platform_api.discovery.categories import (
    AGENT_CATEGORIES,
    get_category_metadata,
)

logger = logging.getLogger(__name__)

DEFAULT_AGENT_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "EDA Analyst",
        "description": "Profiles datasets and generates statistical exploration outputs.",
        "category": "eda",
        "capabilities": ["profiling", "descriptive_stats", "visualization", "eda"],
        "cost_tier": "low",
        "tags": ["data", "exploration", "profiling"],
        "status": "healthy",
    },
    {
        "name": "Data Cleaning Agent",
        "description": "Cleans datasets, fixes missing values, and normalizes data quality issues.",
        "category": "eda",
        "capabilities": ["data_cleaning", "imputation", "type_fixing"],
        "cost_tier": "low",
        "tags": ["data", "preprocessing", "quality"],
        "status": "healthy",
    },
    {
        "name": "Model Trainer",
        "description": "Runs training, evaluation, and model selection workflows.",
        "category": "machine_learning",
        "capabilities": ["training", "evaluation", "forecasting", "classification"],
        "cost_tier": "medium",
        "tags": ["ml", "training", "forecasting"],
        "status": "degraded",
    },
    {
        "name": "Anomaly Detection Agent",
        "description": "Detects drift, outliers, and unusual behavior in datasets and runs.",
        "category": "machine_learning",
        "capabilities": ["anomaly_detection", "monitoring", "alerting"],
        "cost_tier": "medium",
        "tags": ["ml", "monitoring", "alerts"],
        "status": "healthy",
    },
    {
        "name": "Narrative Synthesizer",
        "description": "Builds executive summaries and strategy narratives from workflow outputs.",
        "category": "strategy",
        "capabilities": ["reporting", "summarization", "storytelling"],
        "cost_tier": "low",
        "tags": ["reports", "strategy", "executive"],
        "status": "offline",
    },
    {
        "name": "HITL Coordinator",
        "description": "Adds review checkpoints and approval gates without blocking the pipeline.",
        "category": "human_in_the_loop",
        "capabilities": ["approval", "review", "human_in_the_loop"],
        "cost_tier": "low",
        "tags": ["governance", "approval", "hitl"],
        "status": "healthy",
    },
]


class AgentDiscoveryService:
    """Multi-surface agent discovery: Search, Browse, Recommendation.
    
    This service provides three discovery surfaces:
    1. Search: Natural language search using Pinecone vector similarity
    2. Browse: Category-based browsing for exploration
    3. Recommendation: Workflow-based agent recommendations
    
    Example
    -------
    >>> service = AgentDiscoveryService()
    >>> results = await service.search("detect anomalies in my data")
    >>> agents = await service.browse(category="machine_learning")
    >>> recommendations = await service.recommend(workflow_spec)
    """
    
    INDEX_NAMESPACE = "agents"
    
    def __init__(self, pinecone_api_key: Optional[str] = None, index_name: Optional[str] = None):
        self._pinecone_api_key = pinecone_api_key or getattr(settings, "PINECONE_API_KEY", "")
        self._index_name = index_name or getattr(settings, "PINECONE_INDEX_NAME", "agent-discovery")
        self._index = None
        
        if self._pinecone_api_key:
            self._init_pinecone()

    def _get_catalog(self) -> List[Dict[str, Any]]:
        """Return the registered catalog, or a curated fallback when empty."""
        catalog = AgentRegistry.to_catalog()
        if catalog:
            return catalog
        return [dict(agent) for agent in DEFAULT_AGENT_CATALOG]
    
    def _init_pinecone(self) -> None:
        """Initialize Pinecone client and index."""
        try:
            from pinecone import Pinecone
            
            pc = Pinecone(api_key=self._pinecone_api_key)
            self._index = pc.Index(self._index_name)
            logger.info("Initialized Pinecone index: %s", self._index_name)
        except ImportError:
            logger.warning("Pinecone not installed. Search will use fallback.")
        except Exception as e:
            logger.warning("Failed to initialize Pinecone: %s", e)
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search agents by natural language query.
        
        Parameters
        ----------
        query : str
            Natural language search query.
        filters : Optional[Dict[str, Any]]
            Filters to apply (e.g., {"category": "machine_learning"}).
        top_k : int
            Maximum number of results to return.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of matching agents with scores.
        """
        if self._index:
            return await self._vector_search(query, filters, top_k)
        else:
            return await self._fallback_search(query, filters, top_k)
    
    async def _vector_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search via Pinecone.
        
        Parameters
        ----------
        query : str
            Search query.
        filters : Optional[Dict[str, Any]]
            Metadata filters.
        top_k : int
            Maximum results.
        
        Returns
        -------
        List[Dict[str, Any]]
            Search results.
        """
        try:
            results = self._index.search(
                namespace=self.INDEX_NAMESPACE,
                query={"top_k": top_k, "filter": filters or {}},
                text=query,
            )
            
            return [self._format_result(r) for r in results.matches]
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return await self._fallback_search(query, filters, top_k)
    
    async def _fallback_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Fallback search using keyword matching.
        
        Parameters
        ----------
        query : str
            Search query.
        filters : Optional[Dict[str, Any]]
            Metadata filters.
        top_k : int
            Maximum results.
        
        Returns
        -------
        List[Dict[str, Any]]
            Search results.
        """
        catalog = self._get_catalog()
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for agent in catalog:
            score = 0
            
            name = agent.get("name", "").lower()
            description = agent.get("description", "").lower()
            capabilities = [c.lower() for c in agent.get("capabilities", [])]
            
            for word in query_words:
                if word in name:
                    score += 3
                if word in description:
                    score += 1
                for cap in capabilities:
                    if word in cap:
                        score += 2
            
            if filters:
                if filters.get("category") and agent.get("category") != filters["category"]:
                    continue
                if filters.get("capabilities"):
                    if not any(c in agent.get("capabilities", []) for c in filters["capabilities"]):
                        continue
            
            if score > 0:
                scored.append((agent, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {**agent, "score": score}
            for agent, score in scored[:top_k]
        ]
    
    async def browse(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        cost_tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Browse agents by category, tags, or capabilities.
        
        Parameters
        ----------
        category : Optional[str]
            Filter by category.
        tags : Optional[List[str]]
            Filter by tags.
        capabilities : Optional[List[str]]
            Filter by capabilities.
        cost_tier : Optional[str]
            Filter by cost tier.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of matching agents.
        """
        catalog = self._get_catalog()
        
        if category:
            catalog = [a for a in catalog if a.get("category") == category]
        
        if tags:
            catalog = [
                a for a in catalog
                if any(t in a.get("tags", []) for t in tags)
            ]
        
        if capabilities:
            catalog = [
                a for a in catalog
                if any(c in a.get("capabilities", []) for c in capabilities)
            ]
        
        if cost_tier:
            catalog = [a for a in catalog if a.get("cost_tier") == cost_tier]
        
        return catalog
    
    async def recommend(
        self,
        workflow_spec: Dict[str, Any],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Recommend agents based on workflow context.
        
        Parameters
        ----------
        workflow_spec : Dict[str, Any]
            The workflow specification.
        top_k : int
            Maximum recommendations.
        
        Returns
        -------
        List[Dict[str, Any]]
            Recommended agents.
        """
        required_capabilities = self._extract_capabilities(workflow_spec)
        
        candidates = await self._find_by_capabilities(required_capabilities)
        
        ranked = self._rank_recommendations(candidates, workflow_spec)
        
        return ranked[:top_k]
    
    def _extract_capabilities(self, workflow_spec: Dict[str, Any]) -> List[str]:
        """Extract required capabilities from a workflow spec.
        
        Parameters
        ----------
        workflow_spec : Dict[str, Any]
            The workflow specification.
        
        Returns
        -------
        List[str]
            Required capabilities.
        """
        capabilities = set()
        
        steps = workflow_spec.get("steps", [])
        for step in steps:
            agent_name = step.get("agent", "")
            agent = AgentRegistry.get_or_none(agent_name)
            if agent:
                capabilities.update(agent.capabilities)
        
        description = workflow_spec.get("description", "").lower()
        for category_data in AGENT_CATEGORIES.values():
            for cap in category_data.get("capabilities", []):
                if cap.replace("_", " ") in description:
                    capabilities.add(cap)
        
        return list(capabilities)
    
    async def _find_by_capabilities(
        self,
        capabilities: List[str],
    ) -> List[Dict[str, Any]]:
        """Find agents with matching capabilities.
        
        Parameters
        ----------
        capabilities : List[str]
            Required capabilities.
        
        Returns
        -------
        List[Dict[str, Any]]
            Matching agents with overlap scores.
        """
        catalog = self._get_catalog()
        
        scored = []
        for agent in catalog:
            agent_caps = set(agent.get("capabilities", []))
            overlap = len(set(capabilities) & agent_caps)
            if overlap > 0:
                scored.append((agent, overlap))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {**agent, "capability_overlap": overlap}
            for agent, overlap in scored
        ]
    
    def _rank_recommendations(
        self,
        candidates: List[Dict[str, Any]],
        workflow_spec: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Rank agent recommendations.
        
        Parameters
        ----------
        candidates : List[Dict[str, Any]]
            Candidate agents.
        workflow_spec : Dict[str, Any]
            The workflow specification.
        
        Returns
        -------
        List[Dict[str, Any]]
            Ranked recommendations.
        """
        existing_agents = set()
        for step in workflow_spec.get("steps", []):
            existing_agents.add(step.get("agent", ""))
        
        ranked = []
        for candidate in candidates:
            if candidate.get("name") in existing_agents:
                continue
            ranked.append(candidate)
        
        return ranked
    
    def _format_result(self, result: Any) -> Dict[str, Any]:
        """Format a search result.
        
        Parameters
        ----------
        result : Any
            Pinecone search result.
        
        Returns
        -------
        Dict[str, Any]
            Formatted result.
        """
        return {
            "id": result.id,
            "score": result.score,
            "metadata": result.metadata,
        }

    def _check_threshold(
        self,
        current_value: float,
        threshold: str,
        metrics: Dict[str, Any],
    ) -> bool:
        """Check whether a metric exceeds a rollback-style threshold."""
        if "x_baseline" in threshold:
            multiplier = float(threshold.replace("x_baseline", ""))
            baseline_values = metrics.get("baseline", {})
            baseline = next(iter(baseline_values.values()), 1.0)
            return current_value > baseline * multiplier

        if threshold.endswith("ms"):
            return current_value > float(threshold[:-2])

        if threshold.endswith("%"):
            return current_value < float(threshold[:-1])

        return current_value > float(threshold)
    
    async def index_agents(self) -> int:
        """Index all agents in Pinecone.
        
        Returns
        -------
        int
            Number of agents indexed.
        """
        if not self._index:
            logger.warning("Pinecone not initialized. Cannot index agents.")
            return 0
        
        catalog = self._get_catalog()
        
        vectors = []
        for agent in catalog:
            text = f"{agent['name']}: {agent.get('description', '')}"
            text += f" Capabilities: {', '.join(agent.get('capabilities', []))}"
            text += f" Category: {agent.get('category', 'general')}"
            
            vectors.append({
                "id": agent["name"],
                "values": [0.0] * 1536,
                "metadata": {
                    "name": agent["name"],
                    "description": agent.get("description", ""),
                    "category": agent.get("category", "general"),
                    "capabilities": agent.get("capabilities", []),
                    "cost_tier": agent.get("cost_tier", "medium"),
                },
            })
        
        if vectors:
            self._index.upsert(vectors=vectors, namespace=self.INDEX_NAMESPACE)
            logger.info("Indexed %d agents in Pinecone", len(vectors))
        
        return len(vectors)
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available categories.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of categories with metadata.
        """
        return [
            {
                "key": key,
                **get_category_metadata(key),
            }
            for key in AGENT_CATEGORIES.keys()
        ]
