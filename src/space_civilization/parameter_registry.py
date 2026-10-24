"""V2 simulator parameter SSOT and fail-closed validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


class ParameterError(ValueError):
    """Parameter registry contract violation."""


@dataclass(frozen=True)
class ParameterDefinition:
    parameter_id: str
    label: str
    phase: str
    minimum: int = 0
    maximum: int = 100
    default: int = 50
    unit: str = "index"
    owner: str = "user"
    epistemic_class: str = "model_assumption"


ALLOCATION_IDS = (
    "transport", "autonomy", "life_support", "energy", "domestic_supply",
    "people_research", "international_connection", "open_platform",
)
STRATEGY_IDS = (
    "domestic_procurement", "technology_openness", "dependency_tolerance",
    "short_term_orientation", "risk_tolerance",
)
INITIAL_STATE_IDS = (
    "technology_readiness", "industrial_capacity", "talent_base", "public_support",
)
UNCERTAINTY_IDS = (
    "launch_cost_pressure", "supply_disruption", "international_friction",
)

PARAMETER_REGISTRY = {
    item.parameter_id: item
    for item in (
        *(ParameterDefinition(key, key.replace("_", " "), "economic_organizational", default=12) for key in ALLOCATION_IDS),
        *(ParameterDefinition(key, key.replace("_", " "), "economic_organizational") for key in STRATEGY_IDS),
        *(ParameterDefinition(key, key.replace("_", " "), "physical_material" if key != "public_support" else "cognitive_cultural") for key in INITIAL_STATE_IDS),
        *(ParameterDefinition(key, key.replace("_", " "), "external_uncertainty") for key in UNCERTAINTY_IDS),
    )
}

_BALANCED_ALLOCATIONS = (13, 13, 12, 12, 13, 13, 12, 12)


def _preset(allocations: tuple[int, ...], overrides: dict[str, int]) -> dict[str, int]:
    result = {key: value for key, value in zip(ALLOCATION_IDS, allocations, strict=True)}
    result.update({key: definition.default for key, definition in PARAMETER_REGISTRY.items() if key not in result})
    result.update(overrides)
    return result


PRESETS = {
    "balanced": _preset(_BALANCED_ALLOCATIONS, {}),
    "international": _preset((14, 8, 10, 10, 8, 12, 25, 13), {"dependency_tolerance": 70, "international_friction": 35}),
    "domestic": _preset((15, 12, 10, 10, 25, 18, 5, 5), {"domestic_procurement": 80, "industrial_capacity": 65}),
    "open_platform": _preset((10, 15, 8, 10, 8, 14, 10, 25), {"technology_openness": 85, "talent_base": 70}),
}


def validate_parameters(values: dict[str, int]) -> dict[str, int]:
    if set(values) != set(PARAMETER_REGISTRY):
        missing = sorted(set(PARAMETER_REGISTRY) - set(values))
        extra = sorted(set(values) - set(PARAMETER_REGISTRY))
        raise ParameterError(f"parameter keys differ; missing={missing}, extra={extra}")
    for key, definition in PARAMETER_REGISTRY.items():
        value = values[key]
        if type(value) is not int:
            raise ParameterError(f"{key} must be a strict integer")
        if not definition.minimum <= value <= definition.maximum:
            raise ParameterError(f"{key} must be in {definition.minimum}..{definition.maximum}")
    if sum(values[key] for key in ALLOCATION_IDS) != 100:
        raise ParameterError("eight allocations must sum to 100")
    return deepcopy(values)


def expand_preset(name: str) -> dict[str, int]:
    if name not in PRESETS:
        raise ParameterError(f"unknown preset: {name}")
    return validate_parameters(deepcopy(PRESETS[name]))
