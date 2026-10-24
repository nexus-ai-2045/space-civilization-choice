"""Finite action allowlist owned by the deterministic V2 core."""

from __future__ import annotations

from copy import deepcopy


ACTION_CATALOG = {
    "fund_transport": {"cost": {"budget": 4, "people": 2, "time": 2}, "effects": {"access_and_operation": 4, "public_legitimacy": 1}},
    "deploy_autonomy": {"cost": {"budget": 3, "people": 3, "time": 2}, "effects": {"access_and_operation": 2, "industrial_reproduction": 2}},
    "harden_life_support": {"cost": {"budget": 4, "people": 2, "time": 3}, "effects": {"access_and_operation": 3, "knowledge_continuity": 1}},
    "build_energy_capacity": {"cost": {"budget": 4, "people": 2, "time": 3}, "effects": {"access_and_operation": 3, "industrial_reproduction": 1}},
    "localize_supply": {"cost": {"budget": 3, "people": 3, "time": 2}, "effects": {"industrial_reproduction": 4, "relationship_choice": 2}},
    "train_people": {"cost": {"budget": 2, "people": 3, "time": 3}, "effects": {"knowledge_continuity": 4, "public_legitimacy": 1}},
    "negotiate_standards": {"cost": {"budget": 2, "people": 2, "time": 2}, "effects": {"rule_shaping": 4, "relationship_choice": 2}},
    "open_interfaces": {"cost": {"budget": 2, "people": 3, "time": 2}, "effects": {"rule_shaping": 2, "industrial_reproduction": 2, "public_legitimacy": 1}},
}


def get_action(action_id: str) -> dict:
    if action_id not in ACTION_CATALOG:
        raise ValueError(f"action is not allowlisted: {action_id}")
    return deepcopy(ACTION_CATALOG[action_id])
