from src.audit import AuditLedger
from src.governance import ApprovalRequest, GovernanceEngine
from src.models import ActorRole
from src.processors import ProcessorNode, ProcessorOrchestrator


def test_rbac_blocks_unauthorised_approval():
    audit = AuditLedger()
    governance = GovernanceEngine(audit)
    request = ApprovalRequest(
        "APR-1", "CASE-1", "LEGAL_REVIEW",
        ActorRole.PRIVACY_ANALYST, "Litigation hold detected",
    )
    governance.request(request)
    decision = governance.decide(
        request, ActorRole.PRIVACY_ANALYST, True, "Attempted approval"
    )
    assert decision.approved is False
    assert decision.decided_by == ActorRole.PRIVACY_ANALYST
    assert audit.verify_integrity() is True


def test_legal_reviewer_can_approve_legal_review():
    audit = AuditLedger()
    governance = GovernanceEngine(audit)
    request = ApprovalRequest(
        "APR-2", "CASE-2", "LEGAL_REVIEW",
        ActorRole.PRIVACY_ANALYST, "Retention conflict",
    )
    decision = governance.decide(
        request, ActorRole.LEGAL_REVIEWER, True, "Reviewed retention basis"
    )
    assert decision.approved is True


def test_processor_acknowledgement_is_verified():
    audit = AuditLedger()
    processors = [ProcessorNode("Mail Processor", "marketing")]
    results = ProcessorOrchestrator(processors, audit).propagate(
        "CONS-2", "WITHDRAW_CONSENT"
    )
    assert results[0].success is True
    assert results[0].verified is True
    assert results[0].attempts == 1
    assert processors[0].status == "ACKNOWLEDGED"
    assert audit.verify_integrity() is True


def test_processor_failure_is_visible_after_retries():
    audit = AuditLedger()
    processors = [
        ProcessorNode(
            "Unresponsive Processor",
            "marketing",
            acknowledgement_required=True,
            auto_acknowledge=False,
        )
    ]
    results = ProcessorOrchestrator(processors, audit).propagate(
        "CONS-3", "WITHDRAW_CONSENT", max_retries=2
    )
    assert results[0].success is False
    assert results[0].verified is False
    assert results[0].attempts == 3
    assert results[0].status == "PENDING_ACKNOWLEDGEMENT"
    assert audit.verify_integrity() is True
