from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


def get_tool_call_names(messages: Sequence[BaseMessage]) -> List[str]:
    """
    Extract tool call names from a list of LangChain messages.

    Parameters:
    ----------
    messages : Sequence[BaseMessage]
        A list of LangChain messages.

    Returns:
    -------
    List[str]
        A list of tool call names.
    """
    tool_calls: List[str] = []
    for message in messages:
        try:
            if "tool_call_id" in list(dict(message).keys()):
                tool_calls.append(message.name)
        except Exception as e:
            logger.debug("Failed to extract tool call from message: %s", e)
    return tool_calls


def get_last_user_message_content(messages: Sequence[BaseMessage]) -> str:
    """
    Returns the content of the most recent human/user message in a list.
    Falls back to an empty string when missing.
    """
    for msg in reversed(messages or []):
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if role in ("human", "user"):
            return (getattr(msg, "content", "") or "").strip()
    return ""


def extract_artifact_from_message(msg: BaseMessage) -> Optional[Dict[str, Any]]:
    """
    Extract artifact dictionary from a message if present.

    This is a common pattern repeated across multiple agent files.

    Parameters:
    ----------
    msg : BaseMessage
        A LangChain message that may contain an artifact attribute.

    Returns:
    -------
    Optional[Dict[str, Any]]
        The artifact dictionary if present and valid, None otherwise.
    """
    if not hasattr(msg, "artifact"):
        return None
    artifact = getattr(msg, "artifact", None)
    if not isinstance(artifact, dict):
        return None
    return artifact
