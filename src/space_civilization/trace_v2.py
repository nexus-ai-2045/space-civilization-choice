"""Tamper-evident V2 event trace."""

from __future__ import annotations

from copy import deepcopy

from .simulation import sha256_json


def append_trace(trace: list[dict], payload: dict) -> dict:
    record = {"sequence": len(trace) + 1, "previous_hash": trace[-1]["record_hash"] if trace else None, "payload": deepcopy(payload)}
    record["record_hash"] = sha256_json(record)
    trace.append(record)
    return record


def verify_trace(trace: list[dict]) -> bool:
    previous = None
    for sequence, record in enumerate(trace, start=1):
        if record.get("sequence") != sequence or record.get("previous_hash") != previous:
            return False
        material = {key: deepcopy(value) for key, value in record.items() if key != "record_hash"}
        if record.get("record_hash") != sha256_json(material):
            return False
        previous = record["record_hash"]
    return True
