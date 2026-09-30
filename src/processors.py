from dataclasses import dataclass

from .audit import AuditLedger


@dataclass
class ProcessorNode:
    name: str
    purpose: str
    acknowledgement_required: bool = True
    auto_acknowledge: bool = True
    attempts: int = 0
    status: str = "PENDING"


@dataclass(frozen=True)
class ProcessorResult:
    processor: str
    action: str
    success: bool
    verified: bool
    attempts: int
    status: str
    detail: str


class ProcessorOrchestrator:
    """Simulates controller-to-processor propagation with acknowledgement and retry state."""

    def __init__(self, processors: list[ProcessorNode], audit: AuditLedger):
        self.processors = processors
        self.audit = audit

    def propagate(self, case_id: str, action: str, max_retries: int = 2) -> list[ProcessorResult]:
        results = []
        for processor in self.processors:
            attempts = 0
            acknowledged = False

            while attempts <= max_retries:
                attempts += 1
                processor.attempts = attempts
                self.audit.append(
                    case_id,
                    "PROCESSOR_PROPAGATION_ATTEMPT",
                    {
                        "processor": processor.name,
                        "action": action,
                        "attempt": attempts,
                    },
                )

                if not processor.acknowledgement_required or processor.auto_acknowledge:
                    acknowledged = True
                    break

            if acknowledged:
                processor.status = "ACKNOWLEDGED"
                result = ProcessorResult(
                    processor.name,
                    action,
                    True,
                    True,
                    attempts,
                    processor.status,
                    "Processor acknowledged the propagated privacy action",
                )
            else:
                processor.status = "PENDING_ACKNOWLEDGEMENT"
                result = ProcessorResult(
                    processor.name,
                    action,
                    False,
                    False,
                    attempts,
                    processor.status,
                    "Processor did not acknowledge within retry limit",
                )

            results.append(result)
            self.audit.append(
                case_id,
                "PROCESSOR_PROPAGATION_RESULT",
                {
                    "processor": result.processor,
                    "action": result.action,
                    "success": result.success,
                    "verified": result.verified,
                    "attempts": result.attempts,
                    "status": result.status,
                },
            )
        return results
