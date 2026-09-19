"""Shared TypeSafe System One helper.

Every call here fails soft: a missing TYPESAFE_API_KEY, a network error, or
the SDK not being importable all return None instead of raising, so callers
fall back to their own heuristic rather than breaking an otherwise-working
tool over an optional judgment call.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from typesafe_sdk import Choice, Noul, Score
except ImportError:
    # typesafe-sdk is an optional extra (`pip install nexus-dev-toolkit[typesafe]`).
    # Callers must check these for None before building question objects with
    # them, so a plain install never fails on import.
    Choice = None
    Noul = None
    Score = None


def system_one(state: Any, questions: dict) -> Any | None:
    """Synchronous System One call, for use inside non-async code paths."""
    try:
        from typesafe_sdk import TypeSafeClient
    except ImportError:
        return None
    try:
        with TypeSafeClient() as client:
            return client.system_one(state=state, questions=questions)
    except Exception as e:
        logger.warning("TypeSafe judgment unavailable, falling back to heuristic: %s", e)
        return None


async def system_one_async(state: Any, questions: dict) -> Any | None:
    """Async System One call, for use inside `async def` MCP tools."""
    try:
        from typesafe_sdk import AsyncTypeSafeClient
    except ImportError:
        return None
    try:
        async with AsyncTypeSafeClient() as client:
            return await client.system_one(state=state, questions=questions)
    except Exception as e:
        logger.warning("TypeSafe judgment unavailable, falling back to heuristic: %s", e)
        return None
