from __future__ import annotations


from collections.abc import Sequence
from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .state import TEAM_MAX_MESSAGE_CHARS, TEAM_MAX_MESSAGES, _clean_messages


def trim_messages(
    msgs: Sequence[BaseMessage],
    max_messages: int = TEAM_MAX_MESSAGES,
    max_chars: int = TEAM_MAX_MESSAGE_CHARS,
) -> list[BaseMessage]:
    trimmed: list[BaseMessage] = []
    for message in list(msgs or [])[-max_messages:]:
        content = getattr(message, "content", "")
        if isinstance(content, str) and len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated]..."
            if isinstance(message, AIMessage):
                message = AIMessage(
                    content=content,
                    name=getattr(message, "name", None),
                    id=getattr(message, "id", None),
                )
            elif isinstance(message, HumanMessage):
                message = HumanMessage(content=content, id=getattr(message, "id", None))
            elif isinstance(message, SystemMessage):
                message = SystemMessage(content=content, id=getattr(message, "id", None))
        trimmed.append(message)
    return trimmed


def merge_messages(before_messages: Sequence[BaseMessage], response: dict) -> dict:
    response_msgs = list(response.get("messages") or [])
    if not response_msgs:
        return {"messages": []}

    before_ids = {
        getattr(message, "id", None)
        for message in (before_messages or [])
        if getattr(message, "id", None) is not None
    }

    new_msgs: list[BaseMessage] = []
    seen_new_ids: set[str] = set()
    for message in response_msgs:
        message_id = getattr(message, "id", None)
        if message_id is not None and message_id in before_ids:
            continue
        role = getattr(message, "type", None) or getattr(message, "role", None)
        if role in ("assistant", "ai") or isinstance(message, AIMessage):
            if message_id is not None and message_id in seen_new_ids:
                continue
            new_msgs.append(message)
            if message_id is not None:
                seen_new_ids.add(message_id)

    if not new_msgs:
        for message in reversed(response_msgs):
            role = getattr(message, "type", None) or getattr(message, "role", None)
            if role in ("assistant", "ai") or isinstance(message, AIMessage):
                new_msgs = [message]
                break

    new_msgs = _clean_messages(new_msgs)  # type: ignore[assignment]
    new_msgs = trim_messages(new_msgs)
    return {"messages": new_msgs}


def tag_messages(msgs: Sequence[BaseMessage], default_name: str):
    tagged: list[BaseMessage] = []
    for message in msgs or []:
        if isinstance(message, AIMessage) and not getattr(message, "name", None):
            tagged.append(
                AIMessage(
                    content=getattr(message, "content", "") or "",
                    name=default_name,
                    id=getattr(message, "id", None),
                )
            )
        else:
            tagged.append(message)
    return tagged


def append_error_message(
    merged: dict,
    agent_name: str,
    error_text: Optional[str],
    log_path: Optional[str] = None,
    prefix: str = "Error",
):
    if not error_text:
        return
    lines = [str(error_text)]
    if isinstance(log_path, str) and log_path:
        lines.append(f"Log: {log_path}")
    merged["messages"].append(
        AIMessage(content=f"{prefix}:\n" + "\n".join(lines), name=agent_name)
    )
