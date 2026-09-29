from datetime import date
import copy

from src.audit import AuditLedger
from src.connectors import MockSystemConnector
from src.engine import PrivacyOpsEngine
from src.models import DSRRequest, DataRecord, RequestType
from src.rules import RulesEngine


CONFIG = {
    "jurisdictions": {
        "GDPR": {"response_days": 30, "extension_days": 60},
        "DPDP": {"response_days": None, "extension_days": 0},
    },
    "retention_rules": {
        "litigation": {"action": "PRESERVE"},
        "analytics": {"action": "ANONYMIZE"},
    },
}


def make_engine(records, request_type=RequestType.ERASURE, assurance=3):
    req = DSRRequest("DSR-TEST", "user@example.com", request_type, "GDPR", date(2026, 9, 29))
    return PrivacyOpsEngine(req, RulesEngine(CONFIG),
                            [MockSystemConnector("CRM", copy.deepcopy(records))],
                            AuditLedger()), req


def test_successful_erasure_is_verified():
    engine, _ = make_engine([DataRecord("CRM", "1", {"email": "user@example.com", "name": "A"})])
    result = engine.run()
    assert result["status"] == "FULFILLED"
    assert result["results"][0]["verified"] is True


def test_legal_hold_escalates():
    engine, _ = make_engine([DataRecord("CRM", "1", {"email": "user@example.com"}, ["litigation"])])
    result = engine.run()
    assert result["status"] == "ESCALATED"
    assert result["results"][0]["action"] == "LEGAL_REVIEW"


def test_identity_failure_rejects():
    engine, _ = make_engine([DataRecord("CRM", "1", {"email": "user@example.com"})],
                             RequestType.ACCESS, assurance=1)
    result = engine.run(assurance_level=1)
    assert result["status"] == "REJECTED_UNVERIFIED"


def test_audit_ledger_is_tamper_evident():
    engine, _ = make_engine([DataRecord("CRM", "1", {"email": "user@example.com"})])
    result = engine.run()
    assert AuditLedger() .verify_integrity() is True
    ledger = AuditLedger()
    for event in result["audit"]:
        ledger.events.append(event)
    assert ledger.verify_integrity() is True
    ledger.events[0]["event"] = "ALTERED"
    assert ledger.verify_integrity() is False


def test_gdpr_deadline_is_configured_not_hardcoded():
    engine, req = make_engine([])
    result = engine.run()
    assert result["deadline"] == date(2026, 10, 29)
