from datetime import datetime, timezone

from src.audit import AuditLedger
from src.consent import ConsentLedger, ConsentPropagationEngine
from src.models import ConsentRecord, ProcessingSystem


audit = AuditLedger()
ledger = ConsentLedger()

consent = ConsentRecord(
    consent_id="CONS-2026-001",
    subject_email="user@example.com",
    fiduciary="Example Corp",
    purpose="marketing",
    data_categories=["email", "phone"],
    granted_at=datetime.now(timezone.utc),
)

ledger.register(consent, audit)

systems = [
    ProcessingSystem("CRM", "marketing", ["email", "phone"], processor=None),
    ProcessingSystem("Email Provider", "marketing", ["email"], processor="Mail Processor"),
    ProcessingSystem("Analytics", "product-analytics", ["email"], processor="Analytics Provider"),
]

engine = ConsentPropagationEngine(ledger, systems, audit)
results = engine.propagate_withdrawal(consent.consent_id)

print("=== PRIVACYOPS CONSENT ENGINE ===")
print(f"Consent: {consent.consent_id}")
print(f"Status: {ledger.get(consent.consent_id).status.value}")
for result in results:
    print(result)
print(f"Audit integrity: {audit.verify_integrity()}")
