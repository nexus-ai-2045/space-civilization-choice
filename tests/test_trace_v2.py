from copy import deepcopy

from space_civilization.adaptive_loop import run_adaptive_simulation
from space_civilization.parameter_registry import expand_preset
from space_civilization.trace_v2 import verify_trace


def test_trace_is_hash_chained_and_tamper_evident():
    result = run_adaptive_simulation(expand_preset("balanced"), seed=11)
    assert verify_trace(result["trace"])
    changed = deepcopy(result["trace"])
    changed[2]["payload"]["year"] = 9999
    assert not verify_trace(changed)
