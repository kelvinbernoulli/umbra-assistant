"""
Single source of truth for user_id -> Pinecone namespace resolution.

This is a deliberately tiny module — the whole point is that there is
exactly ONE place in the codebase that turns a user_id into a namespace,
so isolation can't drift between call sites. Nothing else should
construct a namespace string manually.
"""

import re

_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


def resolve_namespace(user_id: str) -> str:
    if not user_id or not _SAFE_ID_PATTERN.match(user_id):
        raise ValueError(f"Invalid user_id for namespace resolution: {user_id!r}")
    return f"user-{user_id}"