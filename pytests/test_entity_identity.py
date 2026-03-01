from __future__ import annotations

import pytest

from utils.entity_identity import derive_relationship_child_canonical_uuid


def test_derive_relationship_child_canonical_uuid_deterministic() -> None:
    u1 = derive_relationship_child_canonical_uuid(
        parent_canonical_uuid="parent123",
        relationship_type="subsidiary",
        child_scheme="sec_cik",
        child_value="0000320193",
    )
    u2 = derive_relationship_child_canonical_uuid(
        parent_canonical_uuid="parent123",
        relationship_type="subsidiary",
        child_scheme="sec_cik",
        child_value="0000320193",
    )
    assert u1 == u2
    assert isinstance(u1, str)
    assert len(u1) == 32  # hex format


@pytest.mark.parametrize(
    "kw_override",
    [
        {"relationship_type": "parent"},
        {"child_scheme": "isin"},
        {"child_value": "0000000000"},
    ],
)
def test_derive_relationship_child_canonical_uuid_changes_on_input_change(
    kw_override: dict,
) -> None:
    base_kwargs = dict(
        parent_canonical_uuid="parent123",
        relationship_type="subsidiary",
        child_scheme="sec_cik",
        child_value="0000320193",
    )

    u_base = derive_relationship_child_canonical_uuid(**base_kwargs)
    base_kwargs.update(kw_override)
    u_changed = derive_relationship_child_canonical_uuid(**base_kwargs)

    assert u_base != u_changed
