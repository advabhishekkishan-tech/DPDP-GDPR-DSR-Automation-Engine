import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class AuditLedger:
    """Hash-chained audit ledger for tamper-evidence in the prototype."""

    def __init__(self):
        self.events: list[dict[str, Any]] = []

    def append(self, request_id: str, event: str, detail: dict[str, Any]) -> dict[str, Any]:
        previous_hash = self.events[-1]["event_hash"] if self.events else "GENESIS"
        payload = {
            "request_id": request_id,
            "event": event,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["event_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
        self.events.append(payload)
        return payload

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        for event in self.events:
            expected_payload = {k: event[k] for k in event if k != "event_hash"}
            canonical = json.dumps(expected_payload, sort_keys=True, separators=(",", ":"))
            if event["previous_hash"] != previous:
                return False
            if hashlib.sha256(canonical.encode()).hexdigest() != event["event_hash"]:
                return False
            previous = event["event_hash"]
        return True
