from copy import deepcopy
from .models import DataRecord, ExecutionResult


class MockSystemConnector:
    """In-memory enterprise-system adapter for safe portfolio demonstrations."""

    def __init__(self, name: str, records: list[DataRecord]):
        self.name = name
        self.records = records

    def discover(self, subject_email: str) -> list[DataRecord]:
        return [
            deepcopy(r)
            for r in self.records
            if r.fields.get("email") == subject_email
        ]

    def erase(self, record_id: str) -> ExecutionResult:
        before = len(self.records)
        self.records = [r for r in self.records if r.record_id != record_id]
        deleted = len(self.records) < before
        return ExecutionResult(
            self.name, "ERASE", deleted, False,
            "Record removed from mock store" if deleted else "Record not found",
        )

    def anonymize(self, record_id: str) -> ExecutionResult:
        for record in self.records:
            if record.record_id == record_id:
                original_keys = list(record.fields)
                record.fields = {
                    key: "[ANONYMIZED]" if key in {"email", "name", "phone", "address"}
                    else value
                    for key, value in record.fields.items()
                }
                return ExecutionResult(
                    self.name, "ANONYMIZE", True, self.verify_anonymized(record_id),
                    f"Direct identifiers transformed: {', '.join(original_keys)}",
                )
        return ExecutionResult(self.name, "ANONYMIZE", False, False, "Record not found")

    def restrict(self, record_id: str) -> ExecutionResult:
        for record in self.records:
            if record.record_id == record_id:
                record.fields["_processing_restricted"] = True
                return ExecutionResult(
                    self.name, "RESTRICT", True,
                    self.is_restricted(record_id),
                    "Processing restriction flag applied",
                )
        return ExecutionResult(self.name, "RESTRICT", False, False, "Record not found")

    def verify_absent(self, record_id: str) -> bool:
        return all(r.record_id != record_id for r in self.records)

    def verify_anonymized(self, record_id: str) -> bool:
        for record in self.records:
            if record.record_id == record_id:
                identifiers = {"email", "name", "phone", "address"}
                return all(
                    record.fields.get(key) == "[ANONYMIZED]"
                    for key in identifiers
                    if key in record.fields
                )
        return False

    def is_restricted(self, record_id: str) -> bool:
        return any(
            r.record_id == record_id and r.fields.get("_processing_restricted") is True
            for r in self.records
        )

    def export(self, subject_email: str) -> list[dict]:
        return [
            deepcopy(r.fields)
            for r in self.records
            if r.fields.get("email") == subject_email
        ]
