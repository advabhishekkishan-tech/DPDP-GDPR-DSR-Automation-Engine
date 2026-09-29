from copy import deepcopy
from .models import DataRecord, ExecutionResult


class MockSystemConnector:
    """In-memory enterprise-system adapter for safe portfolio demonstrations."""

    def __init__(self, name: str, records: list[DataRecord]):
        self.name = name
        self.records = records

    def discover(self, subject_email: str) -> list[DataRecord]:
        return [deepcopy(r) for r in self.records if r.fields.get("email") == subject_email]

    def erase(self, record_id: str) -> ExecutionResult:
        before = len(self.records)
        self.records = [r for r in self.records if r.record_id != record_id]
        deleted = len(self.records) < before
        return ExecutionResult(self.name, "ERASE", deleted, False, "Record removed from mock store")

    def verify_absent(self, record_id: str) -> bool:
        return all(r.record_id != record_id for r in self.records)

    def export(self, subject_email: str) -> list[dict]:
        return [deepcopy(r.fields) for r in self.records if r.fields.get("email") == subject_email]
