from dataclasses import dataclass
from datetime import datetime, timezone

from .audit import AuditLedger
from .models import ActorRole


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    case_id: str
    action: str
    requested_by: ActorRole
    reason: str


@dataclass(frozen=True)
class ApprovalDecision:
    approval_id: str
    case_id: str
    action: str
    decided_by: ActorRole
    approved: bool
    reason: str
    decided_at: str


class GovernanceEngine:
    """Small RBAC/approval layer for high-impact PrivacyOps actions."""

    _permissions = {
        ActorRole.REQUESTER: set(),
        ActorRole.PRIVACY_ANALYST: {"ERASE", "ANONYMIZE", "RESTRICT", "CONSENT_WITHDRAW"},
        ActorRole.LEGAL_REVIEWER: {"LEGAL_REVIEW", "ERASE", "RESTRICT", "CONSENT_WITHDRAW"},
        ActorRole.ADMIN: {"*"},
    }

    def __init__(self, audit: AuditLedger):
        self.audit = audit
        self.decisions: dict[str, ApprovalDecision] = {}

    def can_approve(self, role: ActorRole, action: str) -> bool:
        allowed = self._permissions.get(role, set())
        return "*" in allowed or action in allowed

    def request(self, approval: ApprovalRequest) -> ApprovalRequest:
        self.audit.append(
            approval.case_id,
            "APPROVAL_REQUESTED",
            {
                "approval_id": approval.approval_id,
                "action": approval.action,
                "requested_by": approval.requested_by.value,
                "reason": approval.reason,
            },
        )
        return approval

    def decide(
        self,
        approval: ApprovalRequest,
        role: ActorRole,
        approved: bool,
        reason: str,
    ) -> ApprovalDecision:
        permitted = self.can_approve(role, approval.action)
        final_approval = approved and permitted
        decision = ApprovalDecision(
            approval_id=approval.approval_id,
            case_id=approval.case_id,
            action=approval.action,
            decided_by=role,
            approved=final_approval,
            reason=reason if permitted else "Role is not authorised for this action",
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        self.decisions[approval.approval_id] = decision
        self.audit.append(
            approval.case_id,
            "APPROVAL_DECISION",
            {
                "approval_id": approval.approval_id,
                "action": approval.action,
                "decided_by": role.value,
                "approved": final_approval,
                "reason": decision.reason,
            },
        )
        return decision
