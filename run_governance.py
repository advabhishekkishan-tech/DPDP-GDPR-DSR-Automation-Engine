from src.audit import AuditLedger
from src.governance import ApprovalRequest, GovernanceEngine
from src.models import ActorRole
from src.processors import ProcessorNode, ProcessorOrchestrator


audit = AuditLedger()

governance = GovernanceEngine(audit)
approval = ApprovalRequest(
    "APR-2026-001",
    "DSR-2026-001",
    "LEGAL_REVIEW",
    ActorRole.PRIVACY_ANALYST,
    "Litigation hold requires human legal review",
)
governance.request(approval)
decision = governance.decide(
    approval,
    ActorRole.LEGAL_REVIEWER,
    True,
    "Retention obligation reviewed",
)

processors = [
    ProcessorNode("CRM Processor", "customer-management"),
    ProcessorNode("Email Processor", "marketing"),
]
propagation = ProcessorOrchestrator(processors, audit).propagate(
    "DSR-2026-001",
    "LEGAL_REVIEW",
)

print("Approval:", decision)
print("Processor propagation:", propagation)
print("Audit integrity:", audit.verify_integrity())
