from datetime import datetime, timezone

import pytest

from src.audit import AuditLedger
from src.consent import ConsentLedger, ConsentPropagationEngine
from src.models import ConsentRecord, ConsentStatus, ProcessingSystem


def make_consent():
    return ConsentRecord(
        consent_id="CONS-1",
        subject_email="user@example.com",
        fiduciary="Example Corp",
        purpose="marketing",
        data_categories=["email", "phone"],
        granted_at=datetime.now(timezone.utc),
    )


def test_consent_can_be_registered_and_reviewed():
    audit = AuditLedger()
    ledger = ConsentLedger()
    consent = make_consent()

    ledger.register(consent, audit)
    ledger.review("CONS-1", audit)

    assert ledger.get("CONS-1").status == ConsentStatus.ACTIVE
    assert [item["event"] for item in ledger.history] == ["GRANTED", "REVIEWED"]
    assert audit.verify_integrity() is True


def test_duplicate_consent_id_is_rejected():
    ledger = ConsentLedger()
    ledger.register(make_consent())

    with pytest.raises(ValueError):
        ledger.register(make_consent())


def test_withdrawal_propagates_to_matching_systems_and_processors():
    audit = AuditLedger()
    ledger = ConsentLedger()
    ledger.register(make_consent(), audit)

    systems = [
        ProcessingSystem("CRM", "marketing", ["email", "phone"]),
        ProcessingSystem(
            "Email Provider", "marketing", ["email"], processor="Mail Processor"
        ),
        ProcessingSystem(
            "Analytics", "product-analytics", ["email"], processor="Analytics Provider"
        ),
    ]

    engine = ConsentPropagationEngine(ledger, systems, audit)
    results = engine.propagate_withdrawal("CONS-1")

    assert ledger.get("CONS-1").status == ConsentStatus.WITHDRAWN
    assert len(results) == 2
    assert all(result.success and result.verified for result in results)
    assert systems[0].consent_active is False
    assert systems[1].consent_active is False
    assert systems[2].consent_active is True
    assert audit.verify_integrity() is True


def test_non_consent_processing_basis_is_not_disabled():
    audit = AuditLedger()
    ledger = ConsentLedger()
    ledger.register(make_consent(), audit)

    systems = [
        ProcessingSystem(
            "Fraud Monitoring",
            "marketing",
            ["email"],
            consent_required=False,
        )
    ]

    results = ConsentPropagationEngine(ledger, systems, audit).propagate_withdrawal(
        "CONS-1"
    )

    assert results[0].action == "NO_ACTION"
    assert results[0].verified is True
    assert systems[0].consent_active is True


def test_status_reports_propagation_state():
    audit = AuditLedger()
    ledger = ConsentLedger()
    ledger.register(make_consent(), audit)
    systems = [ProcessingSystem("CRM", "marketing", ["email"])]

    engine = ConsentPropagationEngine(ledger, systems, audit)
    engine.propagate_withdrawal("CONS-1")

    status = engine.status("CONS-1")
    assert status["status"] == "WITHDRAWN"
    assert status["affected_systems"] == ["CRM"]
    assert status["withdrawal_propagated"] is True
