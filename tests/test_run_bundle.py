from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_civilization.comparison import BRANCHES, compare_simulations
from space_civilization.run_bundle import (
    FIXTURE_ALLOWLIST,
    build_run_bundle,
    canonical_bundle_json,
    verify_run_bundle,
)
from space_civilization.simulation import sha256_json


def test_bundle_is_deterministic_and_wraps_unchanged_core_events():
    first = build_run_bundle(ROOT)
    second = build_run_bundle(ROOT)
    assert first == second
    run_id = first["run_id"]
    assert run_id == sha256_json(
        {
            key: value
            for key, value in first["run_request"].items()
            if key != "run_id"
        }
    )
    assert {
        first[section]["run_id"]
        for section in ("run_request", "event_stream", "replay", "evidence")
    } == {run_id}
    comparison = compare_simulations(
        {branch: ROOT / FIXTURE_ALLOWLIST[branch] for branch in BRANCHES}
    )
    expected_events = [
        event
        for branch in BRANCHES
        for event in comparison["branches"][branch]["events"]
    ]
    records = first["event_stream"]["records"]
    assert [record["event"] for record in records] == expected_events
    assert [record["sequence"] for record in records] == list(range(1, 13))
    assert [record["branch"] for record in records] == [
        branch for branch in BRANCHES for _ in range(4)
    ]
    assert [record["turn_id"] for record in records] == list(range(1, 5)) * 3
    previous = "0" * 64
    for record in records:
        assert record["schema"] == "meta-security-run-event/v1"
        assert record["run_id"] == run_id
        assert record["previous_hash"] == previous
        assert record["event_hash"] == sha256_json(record["event"])
        content = {key: value for key, value in record.items() if key != "record_hash"}
        assert record["record_hash"] == sha256_json(content)
        previous = record["record_hash"]
    assert first["evidence"]["event_stream_head_hash"] == previous
    assert first["event_stream"]["event_count"] == len(records)
    assert first["event_stream"]["event_stream_hash"] == sha256_json(records)
    assert first["evidence"]["event_count"] == len(records)
    assert first["evidence"]["event_stream_hash"] == sha256_json(records)
    verify_run_bundle(first, ROOT)


def test_generation_reads_each_fixture_once_and_reuses_the_loaded_objects(monkeypatch):
    original = Path.read_text
    counts = {str((ROOT / ref).resolve()): 0 for ref in FIXTURE_ALLOWLIST.values()}

    def counted(path, *args, **kwargs):
        resolved = str(path.resolve())
        if resolved in counts:
            counts[resolved] += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    bundle = build_run_bundle(ROOT)
    assert set(counts.values()) == {1}
    assert all(
        fixture["sha256"]
        for fixture in bundle["run_request"]["fixtures"]
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "wrong_run_id",
        "bool_seed",
        "reordered",
        "duplicate",
        "skipped",
        "tamper_rehash_one",
        "missing_branch",
        "extra_branch",
        "unknown_field",
        "wrong_schema",
    ),
)
def test_verifier_rejects_noncanonical_bundle(mutation):
    bundle = build_run_bundle(ROOT)
    records = bundle["event_stream"]["records"]
    if mutation == "wrong_run_id":
        bundle["run_id"] = "f" * 64
    elif mutation == "bool_seed":
        bundle["run_request"]["seed"] = True
    elif mutation == "reordered":
        records[0], records[1] = records[1], records[0]
    elif mutation == "duplicate":
        records[1] = deepcopy(records[0])
    elif mutation == "skipped":
        records.pop(1)
    elif mutation == "tamper_rehash_one":
        records[0]["event"]["action"] = "tampered"
        records[0]["event_hash"] = sha256_json(records[0]["event"])
        content = {
            key: value for key, value in records[0].items() if key != "record_hash"
        }
        records[0]["record_hash"] = sha256_json(content)
    elif mutation == "missing_branch":
        bundle["run_request"]["fixtures"].pop()
    elif mutation == "extra_branch":
        bundle["run_request"]["fixtures"].append(
            deepcopy(bundle["run_request"]["fixtures"][0])
        )
    elif mutation == "unknown_field":
        bundle["replay"]["unexpected"] = True
    else:
        bundle["schema"] = "meta-security-run-bundle/v2"
    with pytest.raises(ValueError):
        verify_run_bundle(bundle, ROOT)


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("event_stream", "records", 0, "sequence"), True),
        (("event_stream", "records", 0, "sequence"), 1.0),
        (
            (
                "event_stream",
                "records",
                0,
                "event",
                "axis_deltas",
                "industrial_reproduction",
            ),
            True,
        ),
        (
            (
                "event_stream",
                "records",
                0,
                "event",
                "axis_deltas",
                "industrial_reproduction",
            ),
            1.0,
        ),
    ),
)
def test_verifier_rejects_equal_but_differently_typed_json_values(path, replacement):
    bundle = build_run_bundle(ROOT)
    target = bundle
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
    with pytest.raises(ValueError):
        verify_run_bundle(bundle, ROOT)


def test_verifier_rejects_fixture_drift(tmp_path):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    bundle = build_run_bundle(tmp_path)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["rounds"][0]["evidence_ref"] += "-drift"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_run_bundle(bundle, tmp_path)


def test_generation_and_verification_reject_duplicate_fixture_keys(tmp_path):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    original = fixture.read_text(encoding="utf-8")
    fixture.write_text(
        original.replace("{", '{"seed": 999,', 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate JSON key: seed"):
        build_run_bundle(tmp_path)

    bundle = build_run_bundle(ROOT)
    with pytest.raises(ValueError, match="duplicate JSON key: seed"):
        verify_run_bundle(bundle, tmp_path)


@pytest.mark.parametrize("constant", ("NaN", "Infinity", "-Infinity"))
def test_generation_and_verification_reject_nonfinite_fixture_numbers(
    tmp_path, constant
):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    original = fixture.read_text(encoding="utf-8")
    fixture.write_text(
        original.replace('"public_legitimacy": 50', f'"public_legitimacy": {constant}', 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-finite JSON number"):
        build_run_bundle(tmp_path)

    bundle = build_run_bundle(ROOT)
    with pytest.raises(ValueError, match="non-finite JSON number"):
        verify_run_bundle(bundle, tmp_path)


def test_generation_rejects_python_equal_but_noncanonical_shared_snapshot(tmp_path):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    original = fixture.read_text(encoding="utf-8")
    fixture.write_text(
        original.replace(
            '"policy_allocator": {"capacity": 50}',
            '"policy_allocator": {"capacity": 50.0}',
            1,
        ),
        encoding="utf-8",
    )
    loaded = {
        branch: json.loads((tmp_path / ref).read_text(encoding="utf-8"))
        for branch, ref in FIXTURE_ALLOWLIST.items()
    }
    compare_simulations(loaded)  # Python equality alone accepts 50 == 50.0.
    with pytest.raises(ValueError, match="fixture JSON number must be an integer"):
        build_run_bundle(tmp_path)


@pytest.mark.parametrize("token", ("1.5", "1e2", "1e999", "2e999"))
def test_generation_rejects_every_fixture_float_token(tmp_path, token):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    original = fixture.read_text(encoding="utf-8")
    fixture.write_text(
        original.replace('"public_legitimacy": 50', f'"public_legitimacy": {token}', 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fixture JSON number must be an integer"):
        build_run_bundle(tmp_path)


@pytest.mark.parametrize("invalid", (True, 7, ""))
def test_generation_rejects_invalid_model_version(tmp_path, invalid):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads((ROOT / ref).read_text(encoding="utf-8"))
        payload["model_version"] = invalid
        target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="model_version"):
        build_run_bundle(tmp_path)


def test_generation_rejects_cross_branch_model_version_drift(tmp_path):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["model_version"] += "-drift"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical input contract"):
        build_run_bundle(tmp_path)


def test_generation_rejects_bool_nested_agent_capacity(tmp_path):
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["initial_state"]["agents"]["policy_allocator"]["capacity"] = True
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="agent capacity"):
        build_run_bundle(tmp_path)


def test_generation_and_replay_reject_negative_zero_fixture_integer(tmp_path):
    bundle = build_run_bundle(ROOT)
    for ref in FIXTURE_ALLOWLIST.values():
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)
    fixture = tmp_path / FIXTURE_ALLOWLIST["domestic_autonomy"]
    original = fixture.read_text(encoding="utf-8")
    mutated = original.replace('"rule_shaping": 0', '"rule_shaping": -0', 1)
    assert mutated != original
    fixture.write_text(mutated, encoding="utf-8")
    with pytest.raises(ValueError, match="non-canonical JSON integer"):
        build_run_bundle(tmp_path)
    with pytest.raises(ValueError, match="non-canonical JSON integer"):
        verify_run_bundle(bundle, tmp_path)


@pytest.mark.parametrize(
    "ref",
    ("../outside.json", "/absolute.json", "fixtures/not-allowlisted.json"),
)
def test_fixture_refs_are_allowlisted_and_cannot_traverse(ref):
    refs = dict(FIXTURE_ALLOWLIST)
    refs["domestic_autonomy"] = ref
    with pytest.raises(ValueError):
        build_run_bundle(ROOT, refs)


def test_cli_writes_atomically_without_overwrite_and_verifies(tmp_path):
    output = tmp_path / "bundle.json"
    command = [sys.executable, str(ROOT / "scripts/run_bundle.py")]
    created = subprocess.run(
        [*command, str(output)], cwd=ROOT, capture_output=True, text=True
    )
    assert created.returncode == 0, created.stderr
    original = output.read_bytes()
    duplicate = subprocess.run(
        [*command, str(output)], cwd=ROOT, capture_output=True, text=True
    )
    assert duplicate.returncode != 0
    assert output.read_bytes() == original
    verified = subprocess.run(
        [*command, "--verify", str(output)], cwd=ROOT, capture_output=True, text=True
    )
    assert verified.returncode == 0, verified.stderr


@pytest.mark.parametrize("location", ("top", "nested", "record"))
def test_cli_verify_rejects_duplicate_json_keys(tmp_path, location):
    bundle = build_run_bundle(ROOT)
    text = canonical_bundle_json(bundle)
    if location == "top":
        text = text.replace("{\n", '{\n  "run_id": "duplicate",\n', 1)
    elif location == "nested":
        marker = '  "run_request": {\n'
        text = text.replace(marker, marker + '    "seed": 0,\n', 1)
    else:
        marker = '        "sequence": 1,\n'
        text = text.replace(marker, marker + '        "sequence": 1,\n', 1)
    path = tmp_path / f"duplicate-{location}.json"
    path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "duplicate JSON key" in completed.stderr


@pytest.mark.parametrize("constant", ("NaN", "Infinity", "-Infinity"))
def test_cli_verify_rejects_nonfinite_bundle_numbers(tmp_path, constant):
    text = canonical_bundle_json(build_run_bundle(ROOT)).replace(
        '"sequence": 1,', f'"sequence": {constant},', 1
    )
    path = tmp_path / f"nonfinite-{constant}.json"
    path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "non-finite JSON number" in completed.stderr


@pytest.mark.parametrize("overflow", ("1e999", "2e999", "-1e999"))
def test_cli_verify_rejects_overflow_bundle_numbers(tmp_path, overflow):
    text = canonical_bundle_json(build_run_bundle(ROOT)).replace(
        '"random_draw": 0.8060476863891415', f'"random_draw": {overflow}', 1
    )
    path = tmp_path / f"overflow-{overflow}.json"
    path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "non-finite JSON number" in completed.stderr


def test_cli_verify_accepts_canonical_core_random_draw_floats(tmp_path):
    path = tmp_path / "bundle.json"
    path.write_text(canonical_bundle_json(build_run_bundle(ROOT)), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "alternate",
    (
        "0.80604768638914149",
        "0.80604768638914150",
        "8.060476863891415e-1",
    ),
)
def test_cli_verify_rejects_alternate_float_token_with_same_binary_value(
    tmp_path, alternate
):
    canonical = "0.8060476863891415"
    assert float(canonical) == float(alternate)
    text = canonical_bundle_json(build_run_bundle(ROOT)).replace(
        f'"random_draw": {canonical}', f'"random_draw": {alternate}', 1
    )
    path = tmp_path / "alternate-float-token.json"
    path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "non-canonical JSON float number" in completed.stderr


def test_cli_verify_rejects_negative_zero_integer_token(tmp_path):
    text = canonical_bundle_json(build_run_bundle(ROOT)).replace(
        '"modifier": 0', '"modifier": -0', 1
    )
    path = tmp_path / "negative-zero-integer.json"
    path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "non-canonical JSON integer" in completed.stderr


def test_cli_verify_allows_noncanonical_whitespace_only(tmp_path):
    text = canonical_bundle_json(build_run_bundle(ROOT)).replace(": ", " :   ")
    path = tmp_path / "whitespace.json"
    path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_bundle.py"), "--verify", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
