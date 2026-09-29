from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class RequestType(str, Enum):
    ACCESS = "ACCESS"
    ERASURE = "ERASURE"


class Decision(str, Enum):
    FULFILL = "FULFILL"
    PARTIAL = "PARTIAL"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"


class ActorRole(str, Enum):
    REQUESTER = "REQUESTER"
    PRIVACY_ANALYST = "PRIVACY_ANALYST"
    LEGAL_REVIEWER = "LEGAL_REVIEWER"
    ADMIN = "ADMIN"


@dataclass
class DSRRequest:
    request_id: str
    subject_email: str
    request_type: RequestType
    jurisdiction: str
    created_at: date
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataRecord:
    system: str
    record_id: str
    fields: dict[str, Any]
    retention_tags: list[str] = field(default_factory=list)
    third_party: str | None = None


@dataclass
class ExecutionResult:
    system: str
    action: str
    success: bool
    verified: bool
    detail: str
