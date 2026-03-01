from __future__ import annotations

import uuid


def derive_relationship_child_canonical_uuid(
    *,
    parent_canonical_uuid: str,
    relationship_type: str,
    child_scheme: str,
    child_value: str,
) -> str:
    """Derive a deterministic canonical UUID for a related child entity.

    IMPORTANT:
    - This does *not* change how `entities.canonical_uuid` is generated globally.
    - This is a pure helper for deterministic derivation when creating a new child
      from a known relationship.

    Spec (roadmap):
        uuid5(NAMESPACE_URL, f"{parent_canonical_uuid}:{relationship_type}:{child_scheme}:{child_value}")

    Returns:
        Hex string (32 chars) to match `entities.canonical_uuid` storage style.
    """

    if not parent_canonical_uuid:
        raise ValueError("parent_canonical_uuid is required")
    if not relationship_type:
        raise ValueError("relationship_type is required")
    if not child_scheme:
        raise ValueError("child_scheme is required")
    if not child_value:
        raise ValueError("child_value is required")

    name = f"{parent_canonical_uuid}:{relationship_type}:{child_scheme}:{child_value}"
    return uuid.uuid5(uuid.NAMESPACE_URL, name).hex
