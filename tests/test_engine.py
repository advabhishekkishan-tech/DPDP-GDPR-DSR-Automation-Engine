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
        "security_investigation": {"action": "RESTRICT"},
    },
}


def make_engine(records, request_type=RequestType.ERASURE):
    req = DSRRequest(
        "DSR-TEST", "user@example.com", request_type, "GDPR",
        date(2026, 9, 29)
    )
    return PrivacyOpsEngine(
        req,
        RulesEngine(CONFIG),
        [MockSystemConnector("CRM", copy.deepcopy(records))],
        AuditLedger(),
    ), req


def test_successful_erasure_is_verified():
    engine, _ = make_engine([
        DataRecord("CRM", "1", {"email": "user@example.com", "name": "A"})
    ])
    result = engine.run()
    assert result["status"] == "FULFILLED"
    assert result["results"][0]["verified"] is True
    assert engine.connectors[0].verify_absent("1") is True


def test_legal_hold_escalates():
    engine, _ = make_engine([
        DataRecord("CRM", "1", {"email": "user@example.com"}, ["litigation"])
    ])
    result = engine.run()
    assert result["status"] == "ESCALATED"
    assert result["results"][0]["action"] == "LEGAL_REVIEW"


def test_identity_failure_rejects():
    engine, _ = make_engine([
        DataRecord("CRM", "1", {"email": "user@example.com"})
    ], RequestType.ACCESS)
    result = engine.run(assurance_level=1)
    assert result["status"] == "REJECTED_UNVERIFIED"


def test_anonymization_is_real_and_verified():
    engine, _ = make_engine([
        DataRecord(
            "CRM", "1",
            {"email": "user@example.com", "name": "A", "plan": "gold"},
            ["analytics"],
        )
    ])
    result = engine.run()
    assert result["status"] == "PARTIAL"
    assert result["results"][0]["action"] == "ANONYMIZE"
    assert result["results"][0]["verified"] is True
    assert engine.connectors[0].records[0].fields["email"] == "[ANONYMIZED]"


def test_restriction_is_real_and_verified():
    engine, _ = make_engine([
        DataRecord(
            "CRM", "1",
            {"email": "user@example.com", "name": "A"},
            ["security_investigation"],
        )
    ])
    result = engine.run()
    assert result["status"] == "PARTIAL"
    assert result["results"][0]["action"] == "RESTRICT"
    assert result["results"][0]["verified"] is True
    assert engine.connectors[0].records[0].fields["_processing_restricted"] is True


def test_access_creates_response_package():
    engine, _ = make_engine([
        DataRecord("CRM", "1", {"email": "user@example.com", "name": "A"})
    ], RequestType.ACCESS)
    result = engine.run()
    assert result["status"] == "FULFILLED"
    assert result["response_package"]["request_type"] == "ACCESS"
    assert result["access_package"][0]["data"]["name"] == "A"


def test_audit_ledger_is_tamper_evident():
    engine, _ = make_engine([
        DataRecord("CRM", "1", {"email": "user@example.com"})
    ])
    result = engine.run()
    ledger = AuditLedger()
    ledger.events.extend(copy.deepcopy(result["audit"]))
    assert ledger.verify_integrity() is True
    ledger.events[0]["event"] = "ALTERED"
    assert ledger.verify_integrity() is False


def test_gdpr_deadline_is_configured_not_hardcoded():
    engine, _ = make_engine([])
    result = engine.run()
    assert result["deadline"] == date(2026, 10, 29)


def test_duplicate_request_is_detected():
    from src.case_management import RequestRegistry

    registry = RequestRegistry()
    assert registry.register("DSR-1", "USER@example.com", "ERASURE") is True
    assert registry.register("DSR-2", "user@example.com", "ERASURE") is False
    assert registry.existing_request("user@example.com", "ERASURE") == "DSR-1"


def test_access_package_is_audited():
    engine, _ = make_engine([
        DataRecord("CRM", "1", {"email": "user@example.com", "name": "A"})
    ], RequestType.ACCESS)
    result = engine.run()
    events = [e["event"] for e in result["audit"]]
    assert "EXECUTION" in events
    assert "CLOSURE" in events
