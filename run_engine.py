from datetime import date
import yaml

from src.audit import AuditLedger
from src.connectors import MockSystemConnector
from src.engine import PrivacyOpsEngine
from src.models import DSRRequest, DataRecord, RequestType
from src.rules import RulesEngine


with open("config/rules.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

records = [
    DataRecord("PostgreSQL", "pg-001", {"email": "user@example.com", "name": "Demo User"}),
    DataRecord("Salesforce", "crm-001", {"email": "user@example.com", "marketing": True}, ["analytics"]),
    DataRecord("Archive", "arc-001", {"email": "user@example.com", "case_ref": "LIT-42"}, ["litigation"]),
]

request = DSRRequest("DSR-2026-V2-001", "user@example.com",
                     RequestType.ERASURE, "GDPR", date.today())

engine = PrivacyOpsEngine(
    request,
    RulesEngine(config),
    [
        MockSystemConnector("PostgreSQL", [records[0]]),
        MockSystemConnector("Salesforce", [records[1]]),
        MockSystemConnector("Archive", [records[2]]),
    ],
    AuditLedger(),
)

result = engine.run(assurance_level=3)
print("=== PRIVACYOPS DSR ENGINE V2 ===")
print(f"Request: {request.request_id}")
print(f"Status: {result['status']}")
print(f"Deadline: {result['deadline']}")
for item in result["results"]:
    print(item)
print(f"Audit integrity: {engine.audit.verify_integrity()}")
