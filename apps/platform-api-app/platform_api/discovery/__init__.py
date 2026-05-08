"""Agent discovery module with Pinecone integration.

This module provides:
- Multi-surface agent discovery (Search, Browse, Recommendation)
- Pinecone vector search for semantic matching
- Category-based browsing
- Workflow-based recommendations
"""

from platform_api.discovery.agent_discovery import AgentDiscoveryService
from platform_api.discovery.categories import AGENT_CATEGORIES

__all__ = [
    "AgentDiscoveryService",
    "AGENT_CATEGORIES",
]
