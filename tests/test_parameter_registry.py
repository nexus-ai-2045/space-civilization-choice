import pytest

from space_civilization.parameter_registry import (
    ALLOCATION_IDS,
    UNCERTAINTY_IDS,
    PARAMETER_REGISTRY,
    ParameterError,
    expand_preset,
    validate_parameters,
)


def test_registry_has_twenty_strict_integer_parameters():
    assert len(PARAMETER_REGISTRY) == 20
    assert len(ALLOCATION_IDS) == 8
    assert len(UNCERTAINTY_IDS) == 3
    values = expand_preset("balanced")
    assert validate_parameters(values) == values
    values["transport"] = True
    with pytest.raises(ParameterError, match="integer"):
        validate_parameters(values)


def test_allocations_must_sum_to_one_hundred():
    values = expand_preset("balanced")
    values["transport"] += 1
    with pytest.raises(ParameterError, match="sum to 100"):
        validate_parameters(values)


def test_preset_is_expanded_and_not_a_transition_rule():
    assert sum(expand_preset("international")[key] for key in ALLOCATION_IDS) == 100
    with pytest.raises(ParameterError, match="unknown preset"):
        expand_preset("magic")
