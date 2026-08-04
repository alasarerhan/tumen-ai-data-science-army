"""Pagination schemas and utilities for list endpoints.

Provides cursor-based pagination for efficient data retrieval without
offset-based performance degradation on large datasets.

Design
------
* **Cursor-based**: Uses record ID as cursor for stable pagination
* **Limit control**: Max 100 items per page to prevent over-fetching
* **Metadata**: Returns has_more, next_cursor, and total_count (optional)

Best Practices Reference:
https://graphql.org/learn/pagination/
https://slack.dev/node-slack/reference#pagination
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    cursor: str | None = Field(
        default=None,
        description="Cursor for the next page (record ID)",
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Number of items per page (max {MAX_PAGE_SIZE})",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper for list endpoints."""

    items: list[T]
    next_cursor: str | None = Field(
        default=None,
        description="Cursor to fetch the next page",
    )
    has_more: bool = Field(
        default=False,
        description="Whether more items are available",
    )
    total_count: int | None = Field(
        default=None,
        description="Total count (expensive, computed only if requested)",
    )


def paginate_query(query, model, cursor: str | None, limit: int, cursor_column=None):
    """Apply pagination to a SQLAlchemy query.

    Parameters
    ----------
    query : Select
        The base SQLAlchemy query.
    model : DeclarativeBase
        The model class for the query.
    cursor : str | None
        The cursor (record ID) to start from.
    limit : int
        Number of items to return. Must be >= 1.
    cursor_column : Column | None
        The column to use for cursor comparison (defaults to model.id).

    Returns
    -------
    Select
        The paginated query.

    Raises
    ------
    ValueError
        If limit is less than 1.
    """

    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")

    column = cursor_column or model.id

    if cursor:
        query = query.where(column < cursor)

    query = query.order_by(column.desc()).limit(limit + 1)

    return query


def build_paginated_response(items: list, limit: int, id_attr: str = "id") -> dict:
    """Build a paginated response from a list of items.

    Parameters
    ----------
    items : list
        List of items (should be limit + 1 items to detect has_more).
    limit : int
        The requested limit. Must be >= 1.
    id_attr : str
        The attribute name for the ID (defaults to "id").

    Returns
    -------
    dict
        Response dict with items, next_cursor, and has_more.

    Raises
    ------
    ValueError
        If limit is less than 1.
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")

    has_more = len(items) > limit
    result_items = items[:limit]

    next_cursor = None
    if has_more and result_items:
        last_item = result_items[-1]
        next_cursor = str(getattr(last_item, id_attr, None))

    return {
        "items": result_items,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
