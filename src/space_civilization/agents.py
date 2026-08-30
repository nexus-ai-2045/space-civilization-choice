"""Canonical organization-level agents for the V2 simulator."""

AGENT_PREFERENCES = {
    "policy_allocator": ("fund_transport", "negotiate_standards", "train_people"),
    "domestic_exploration_alliance": ("harden_life_support", "deploy_autonomy", "fund_transport"),
    "transport_and_components_alliance": ("localize_supply", "build_energy_capacity", "fund_transport"),
    "research_and_next_generation_alliance": ("train_people", "open_interfaces", "deploy_autonomy"),
    "international_partners": ("negotiate_standards", "open_interfaces", "harden_life_support"),
}

AGENT_IDS = tuple(AGENT_PREFERENCES)
