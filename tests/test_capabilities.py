from most.adapters import CapabilitySet, compute_effective_capabilities


def test_discovered_capabilities_and_user_restrictions_are_applied():
    effective = compute_effective_capabilities(
        CapabilitySet(frozenset({"text_input", "text_output", "workspace_access"})),
        CapabilitySet(frozenset({"text_input", "text_output"})),
        CapabilitySet(frozenset({"text_output"})),
    )
    assert effective.values == frozenset({"text_input"})
