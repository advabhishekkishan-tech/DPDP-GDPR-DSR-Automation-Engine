from .audit import AuditLedger
from .connectors import MockSystemConnector
from .models import DSRRequest, Decision, RequestType
from .rules import RulesEngine


class PrivacyOpsEngine:
    def __init__(
        self,
        request: DSRRequest,
        rules: RulesEngine,
        connectors: list[MockSystemConnector],
        audit: AuditLedger,
    ):
        self.request = request
        self.rules = rules
        self.connectors = connectors
        self.audit = audit

    def verify_identity(self, assurance_level: int) -> bool:
        passed = assurance_level >= 2
        self.audit.append(
            self.request.request_id,
            "IDENTITY_CHECK",
            {"assurance_level": assurance_level, "passed": passed},
        )
        return passed

    def discover(self):
        found = []
        for connector in self.connectors:
            records = connector.discover(self.request.subject_email)
            found.extend((connector, record) for record in records)
            self.audit.append(
                self.request.request_id,
                "DISCOVERY",
                {"system": connector.name, "records_found": len(records)},
            )
        return found

    def decide(self, discovered):
        decisions = []
        for connector, record in discovered:
            action = self.rules.retention_action(record.retention_tags)
            decision = (
                Decision.FULFILL if action == "ERASE"
                else Decision.PARTIAL if action in {"RESTRICT", "ANONYMIZE"}
                else Decision.ESCALATE
            )
            decisions.append((connector, record, action, decision))
            self.audit.append(
                self.request.request_id,
                "LEGAL_DECISION",
                {
                    "system": connector.name,
                    "record_id": record.record_id,
                    "retention_tags": record.retention_tags,
                    "action": action,
                    "decision": decision.value,
                },
            )
        return decisions

    def execute(self, decisions):
        results = []
        access_package = []

        for connector, record, action, decision in decisions:
            if self.request.request_type == RequestType.ACCESS:
                exported = connector.export(self.request.subject_email)
                access_package.extend(
                    {"system": connector.name, "data": item} for item in exported
                )
                result = {
                    "system": connector.name,
                    "action": "EXPORT",
                    "success": True,
                    "verified": bool(exported) or not exported,
                    "detail": f"{len(exported)} record(s) prepared for access package",
                }
            elif decision == Decision.ESCALATE:
                result = {
                    "system": connector.name,
                    "action": "LEGAL_REVIEW",
                    "success": False,
                    "verified": False,
                    "detail": "Retention obligation requires human legal review",
                }
            elif decision == Decision.PARTIAL and action == "ANONYMIZE":
                execution = connector.anonymize(record.record_id)
                result = execution.__dict__
            elif decision == Decision.PARTIAL and action == "RESTRICT":
                execution = connector.restrict(record.record_id)
                result = execution.__dict__
            else:
                execution = connector.erase(record.record_id)
                execution.verified = connector.verify_absent(record.record_id)
                result = execution.__dict__

            results.append(result)
            self.audit.append(
                self.request.request_id,
                "EXECUTION",
                result,
            )

            if result["action"] in {"ERASE", "ANONYMIZE", "RESTRICT"}:
                self.audit.append(
                    self.request.request_id,
                    "VERIFICATION",
                    {
                        "system": result["system"],
                        "action": result["action"],
                        "verified": result["verified"],
                    },
                )

        return results, access_package

    def run(self, assurance_level: int = 2):
        deadline = self.rules.deadline(
            self.request.jurisdiction,
            self.request.created_at,
        )
        self.audit.append(
            self.request.request_id,
            "REQUEST_RECEIVED",
            {
                "type": self.request.request_type.value,
                "jurisdiction": self.request.jurisdiction,
                "deadline": deadline.isoformat() if deadline else None,
            },
        )

        if not self.verify_identity(assurance_level):
            self.audit.append(
                self.request.request_id,
                "CLOSURE",
                {
                    "decision": Decision.REJECT.value,
                    "reason": "identity_assurance_insufficient",
                },
            )
            return {
                "status": "REJECTED_UNVERIFIED",
                "deadline": deadline,
                "results": [],
                "access_package": [],
                "audit": self.audit.events,
            }

        discovered = self.discover()
        decisions = self.decide(discovered)
        results, access_package = self.execute(decisions)

        if not results:
            status = "FULFILLED"
        elif any(r.get("action") == "LEGAL_REVIEW" for r in results):
            status = "ESCALATED"
        elif any(r.get("action") in {"RESTRICT", "ANONYMIZE"} for r in results):
            status = "PARTIAL"
        elif all(r.get("verified") for r in results):
            status = "FULFILLED"
        else:
            status = "REJECTED_UNVERIFIED"

        response_package = {
            "request_id": self.request.request_id,
            "request_type": self.request.request_type.value,
            "jurisdiction": self.request.jurisdiction,
            "status": status,
            "deadline": deadline.isoformat() if deadline else None,
            "data": access_package,
        }

        self.audit.append(
            self.request.request_id,
            "CLOSURE",
            {
                "status": status,
                "evidence_items": len(results),
                "access_package_records": len(access_package),
            },
        )
        return {
            "status": status,
            "deadline": deadline,
            "results": results,
            "access_package": access_package,
            "response_package": response_package,
            "audit": self.audit.events,
        }
