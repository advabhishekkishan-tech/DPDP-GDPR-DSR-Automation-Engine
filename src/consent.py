from .audit import AuditLedger
from .models import ConsentRecord, ConsentStatus, ProcessingSystem, PropagationResult


class ConsentLedger:
    """In-memory consent state store for the portfolio prototype."""

    def __init__(self):
        self.records: dict[str, ConsentRecord] = {}
        self.history: list[dict] = []

    def register(self, consent: ConsentRecord, audit: AuditLedger | None = None) -> ConsentRecord:
        if consent.consent_id in self.records:
            raise ValueError(f"Consent already exists: {consent.consent_id}")
        self.records[consent.consent_id] = consent
        self._record_history(consent, "GRANTED", audit)
        return consent

    def get(self, consent_id: str) -> ConsentRecord:
        try:
            return self.records[consent_id]
        except KeyError as exc:
            raise KeyError(f"Unknown consent: {consent_id}") from exc

    def review(self, consent_id: str, audit: AuditLedger | None = None) -> ConsentRecord:
        consent = self.get(consent_id)
        self._record_history(consent, "REVIEWED", audit)
        return consent

    def withdraw(self, consent_id: str, audit: AuditLedger | None = None) -> ConsentRecord:
        consent = self.get(consent_id)
        if consent.status == ConsentStatus.WITHDRAWN:
            return consent
        consent.status = ConsentStatus.WITHDRAWN
        consent.withdrawn_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        self._record_history(consent, "WITHDRAWN", audit)
        return consent

    def _record_history(self, consent: ConsentRecord, event: str, audit: AuditLedger | None):
        item = {
            "consent_id": consent.consent_id,
            "subject_email": consent.subject_email,
            "purpose": consent.purpose,
            "status": consent.status.value,
            "event": event,
        }
        self.history.append(item)
        if audit:
            audit.append(consent.consent_id, f"CONSENT_{event}", item)


class ConsentPropagationEngine:
    """Propagates a consent withdrawal to systems processing data for that purpose."""

    def __init__(
        self,
        ledger: ConsentLedger,
        systems: list[ProcessingSystem],
        audit: AuditLedger,
    ):
        self.ledger = ledger
        self.systems = systems
        self.audit = audit

    def propagate_withdrawal(self, consent_id: str) -> list[PropagationResult]:
        consent = self.ledger.withdraw(consent_id, self.audit)
        results = []

        for system in self.systems:
            purpose_match = system.purpose == consent.purpose
            category_match = bool(set(system.data_categories) & set(consent.data_categories))
            subject_scope = consent.subject_email in system.system

            if not purpose_match or not category_match:
                continue

            if not system.consent_required:
                result = PropagationResult(
                    system.system, system.processor, "NO_ACTION",
                    True, True,
                    "System uses a non-consent processing basis for this purpose",
                )
            else:
                system.consent_active = False
                result = PropagationResult(
                    system.system, system.processor, "WITHDRAW_CONSENT",
                    True, system.consent_active is False,
                    "Consent withdrawal propagated to processing system",
                )

            results.append(result)
            self.audit.append(
                consent.consent_id,
                "CONSENT_PROPAGATION",
                {
                    "system": result.system,
                    "processor": result.processor,
                    "action": result.action,
                    "success": result.success,
                },
            )
            self.audit.append(
                consent.consent_id,
                "CONSENT_VERIFICATION",
                {
                    "system": result.system,
                    "verified": result.verified,
                },
            )

        return results

    def status(self, consent_id: str) -> dict:
        consent = self.ledger.get(consent_id)
        affected = [
            system.system
            for system in self.systems
            if system.purpose == consent.purpose
            and bool(set(system.data_categories) & set(consent.data_categories))
        ]
        return {
            "consent_id": consent.consent_id,
            "status": consent.status.value,
            "purpose": consent.purpose,
            "affected_systems": affected,
            "withdrawal_propagated": all(
                not system.consent_required or not system.consent_active
                for system in self.systems
                if system.system in affected
            ),
        }
