"""TypeSafe judgments (System One), switched on by TYPESAFE_API_KEY.

nexus asks TypeSafe only where it would otherwise guess from keywords — a doc that doesn't follow
the guide, a token name the rules can't place, a stack hint with no package-manager name, a doc
with no "Choice" lines. Explicit sources (guide sections, Choice lines, exact names) always win.

Without the key, nothing is sent and every caller uses its built-in rules. With the key, any
error (network, timeout, bad answer) also falls back — a judgment is never a reason for a tool
to fail. Each caller reports which path answered: "typesafe" or "built-in".
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    from typesafe_sdk import Choice, Noul
except ImportError:  # the SDK is a dependency; this only guards a broken install
    Choice = None
    Noul = None

TIMEOUT_SECONDS = 30.0
TYPESAFE = "typesafe"
BUILT_IN = "built-in"


def enabled() -> bool:
    """True when TYPESAFE_API_KEY is set (and the SDK imports). Checked on every call, so a key
    added to the environment takes effect without restarting anything nexus controls."""
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip()) and Choice is not None


def system_one(state: Any, questions: dict) -> Any | None:
    """Synchronous System One call. None when disabled or on any error."""
    if not enabled() or not questions:
        return None
    try:
        from typesafe_sdk import TypeSafeClient
        with TypeSafeClient(timeout=TIMEOUT_SECONDS) as client:
            return client.system_one(state=state, questions=questions)
    except Exception as e:
        logger.warning("TypeSafe judgment unavailable, using the built-in rules: %s", type(e).__name__)
        return None


async def system_one_async(state: Any, questions: dict) -> Any | None:
    """Async System One call, for `async def` MCP tools. None when disabled or on any error."""
    if not enabled() or not questions:
        return None
    try:
        from typesafe_sdk import AsyncTypeSafeClient
        async with AsyncTypeSafeClient(timeout=TIMEOUT_SECONDS) as client:
            return await client.system_one(state=state, questions=questions)
    except Exception as e:
        logger.warning("TypeSafe judgment unavailable, using the built-in rules: %s", type(e).__name__)
        return None
