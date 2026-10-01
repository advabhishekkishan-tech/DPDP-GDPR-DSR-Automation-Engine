import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.audit import AuditLedger
from src.consent import ConsentLedger, ConsentPropagationEngine
from src.connectors import MockSystemConnector
from src.engine import PrivacyOpsEngine
from src.governance import ApprovalRequest, GovernanceEngine
from src.models import (
    ActorRole,
    ConsentRecord,
    ConsentStatus,
    DataRecord,
    DSRRequest,
    ProcessingSystem,
    RequestType,
)
from src.processors import ProcessorNode, ProcessorOrchestrator
from src.rules import RulesEngine

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "privacyops.db"

app = FastAPI(
    title="PrivacyOps DSR Lab",
    version="1.1.0",
    description="Local PrivacyOps case-management application using the repository's DSR engine.",
)


class DSRSubmission(BaseModel):
    subject_email: str = Field(min_length=3, max_length=320)
    request_type: RequestType = RequestType.ERASURE
    jurisdiction: str = Field(default="GDPR", min_length=2, max_length=32)
    assurance_level: int = Field(default=3, ge=0, le=5)


class ApprovalSubmission(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    role: ActorRole
    approved: bool
    reason: str = Field(default="", max_length=1000)


class ConsentSubmission(BaseModel):
    subject_email: str = Field(min_length=3, max_length=320)
    purpose: str = Field(min_length=1, max_length=200)
    data_categories: list[str] = Field(min_length=1, max_length=50)


def ensure_column(conn, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY, subject_email TEXT NOT NULL, request_type TEXT NOT NULL,
        jurisdiction TEXT NOT NULL, assurance_level INTEGER NOT NULL, status TEXT NOT NULL,
        deadline TEXT, results_json TEXT NOT NULL, response_json TEXT NOT NULL,
        audit_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS consents (
        id TEXT PRIMARY KEY, subject_email TEXT NOT NULL, purpose TEXT NOT NULL,
        data_categories TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
        withdrawn_at TEXT
    )""")
    ensure_column(conn, "consents", "audit_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "consents", "propagation_json", "TEXT NOT NULL DEFAULT '[]'")
    conn.commit()
    return conn


def build_engine(payload: DSRSubmission):
    with open(BASE_DIR / "config" / "rules.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    records = [
        DataRecord(
            "PostgreSQL",
            "pg-001",
            {"email": payload.subject_email, "name": "Demo User", "phone": "+91-9000000000"},
        ),
        DataRecord(
            "Salesforce",
            "crm-001",
            {"email": payload.subject_email, "marketing": True},
            ["analytics"],
        ),
        DataRecord(
            "Archive",
            "arc-001",
            {"email": payload.subject_email, "case_ref": "LIT-42"},
            ["litigation"],
        ),
    ]
    request = DSRRequest(
        request_id=f"WEB-{date.today().isoformat()}-{uuid4().hex[:8]}",
        subject_email=payload.subject_email,
        request_type=payload.request_type,
        jurisdiction=payload.jurisdiction,
        created_at=date.today(),
    )
    return PrivacyOpsEngine(
        request,
        RulesEngine(config),
        [
            MockSystemConnector("PostgreSQL", [records[0]]),
            MockSystemConnector("Salesforce", [records[1]]),
            MockSystemConnector("Archive", [records[2]]),
        ],
        AuditLedger(),
    )


def save_case(request, result):
    conn = db()
    conn.execute(
        """INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            request.request_id,
            request.subject_email,
            request.request_type.value,
            request.jurisdiction,
            request.metadata.get("assurance_level", 2),
            result["status"],
            result["deadline"].isoformat() if result["deadline"] else None,
            json.dumps(result["results"], default=str),
            json.dumps(result.get("response_package", {}), default=str),
            json.dumps(result["audit"], default=str),
            request.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_case(case_id):
    conn = db()
    row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Case not found")
    return dict(row)


def ledger_from_case(case):
    ledger = AuditLedger()
    ledger.events = json.loads(case["audit_json"])
    return ledger


def save_audit(case_id, ledger):
    conn = db()
    conn.execute(
        "UPDATE cases SET audit_json=? WHERE id=?",
        (json.dumps(ledger.events, default=str), case_id),
    )
    conn.commit()
    conn.close()


def consent_from_row(row) -> ConsentRecord:
    return ConsentRecord(
        consent_id=row["id"],
        subject_email=row["subject_email"],
        fiduciary="Example Corp",
        purpose=row["purpose"],
        data_categories=json.loads(row["data_categories"]),
        status=ConsentStatus(row["status"]),
        granted_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc),
        withdrawn_at=(
            datetime.fromisoformat(row["withdrawn_at"]).replace(tzinfo=timezone.utc)
            if row["withdrawn_at"]
            else None
        ),
    )


def consent_systems(consent: ConsentRecord) -> list[ProcessingSystem]:
    return [
        ProcessingSystem("CRM", consent.purpose, consent.data_categories),
        ProcessingSystem(
            "Email Provider",
            consent.purpose,
            consent.data_categories,
            processor="Mail Processor",
        ),
        ProcessingSystem(
            "Analytics",
            "product-analytics",
            consent.data_categories,
            processor="Analytics Provider",
        ),
    ]


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "application": "PrivacyOps DSR Lab", "version": "1.1.0"}


@app.get("/api/cases")
def list_cases():
    conn = db()
    rows = conn.execute(
        "SELECT id, subject_email, request_type, jurisdiction, status, created_at "
        "FROM cases ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str):
    case = get_case(case_id)
    case["results"] = json.loads(case["results_json"])
    case["response_package"] = json.loads(case["response_json"])
    case["audit"] = json.loads(case["audit_json"])
    case["audit_integrity"] = ledger_from_case(case).verify_integrity()
    del case["results_json"], case["response_json"], case["audit_json"]
    return case


@app.post("/api/cases")
def create_case(payload: DSRSubmission):
    conn = db()
    existing = conn.execute(
        "SELECT id FROM cases WHERE lower(subject_email)=lower(?) "
        "AND request_type=? AND jurisdiction=? LIMIT 1",
        (payload.subject_email, payload.request_type.value, payload.jurisdiction),
    ).fetchone()
    conn.close()
    if existing:
        raise HTTPException(
            409,
            detail=f"Duplicate DSR detected. Existing case: {existing['id']}",
        )

    engine = build_engine(payload)
    engine.request.metadata["assurance_level"] = payload.assurance_level
    result = engine.run(assurance_level=payload.assurance_level)
    save_case(engine.request, result)
    return case_detail(engine.request.request_id)


@app.post("/api/cases/{case_id}/approvals")
def approval(case_id: str, payload: ApprovalSubmission):
    case = get_case(case_id)
    ledger = ledger_from_case(case)
    governance = GovernanceEngine(ledger)
    approval_id = f"APR-{uuid4().hex[:8]}"
    request = ApprovalRequest(
        approval_id,
        case_id,
        payload.action,
        ActorRole.PRIVACY_ANALYST,
        payload.reason,
    )
    governance.request(request)
    decision = governance.decide(request, payload.role, payload.approved, payload.reason)
    save_audit(case_id, ledger)
    return decision.__dict__


@app.get("/api/consents")
def list_consents():
    conn = db()
    rows = conn.execute(
        "SELECT id, subject_email, purpose, data_categories, status, created_at, withdrawn_at "
        "FROM consents ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["data_categories"] = json.loads(item["data_categories"])
        item["propagation"] = []
        conn = db()
        saved = conn.execute(
            "SELECT propagation_json FROM consents WHERE id=?", (row["id"],)
        ).fetchone()
        conn.close()
        if saved:
            item["propagation"] = json.loads(saved["propagation_json"])
        result.append(item)
    return result


@app.post("/api/consents")
def create_consent(payload: ConsentSubmission):
    consent_id = f"CONS-{uuid4().hex[:8]}"
    audit = AuditLedger()
    consent = ConsentRecord(
        consent_id=consent_id,
        subject_email=payload.subject_email,
        fiduciary="Example Corp",
        purpose=payload.purpose,
        data_categories=payload.data_categories,
        granted_at=datetime.now(timezone.utc),
    )
    ConsentLedger().register(consent, audit)

    conn = db()
    conn.execute(
        "INSERT INTO consents "
        "(id, subject_email, purpose, data_categories, status, created_at, withdrawn_at, audit_json, propagation_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            consent_id,
            payload.subject_email,
            payload.purpose,
            json.dumps(payload.data_categories),
            ConsentStatus.ACTIVE.value,
            date.today().isoformat(),
            None,
            json.dumps(audit.events),
            "[]",
        ),
    )
    conn.commit()
    conn.close()
    return {"consent_id": consent_id, "status": "ACTIVE", "audit_integrity": audit.verify_integrity()}


@app.post("/api/consents/{consent_id}/withdraw")
def withdraw_consent(consent_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM consents WHERE id=?", (consent_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Consent not found")
    if row["status"] == ConsentStatus.WITHDRAWN.value:
        audit = AuditLedger()
        audit.events = json.loads(row["audit_json"])
        return {
            "consent_id": consent_id,
            "status": ConsentStatus.WITHDRAWN.value,
            "propagation": json.loads(row["propagation_json"]),
            "audit_integrity": audit.verify_integrity(),
        }

    consent = consent_from_row(row)
    ledger = ConsentLedger()
    ledger.records[consent.consent_id] = consent
    audit = AuditLedger()
    audit.events = json.loads(row["audit_json"])
    propagation_engine = ConsentPropagationEngine(
        ledger,
        consent_systems(consent),
        audit,
    )
    results = propagation_engine.propagate_withdrawal(consent_id)

    conn = db()
    conn.execute(
        "UPDATE consents SET status=?, withdrawn_at=?, audit_json=?, propagation_json=? WHERE id=?",
        (
            ConsentStatus.WITHDRAWN.value,
            date.today().isoformat(),
            json.dumps(audit.events, default=str),
            json.dumps([result.__dict__ for result in results], default=str),
            consent_id,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "consent_id": consent_id,
        "status": ConsentStatus.WITHDRAWN.value,
        "propagation": [result.__dict__ for result in results],
        "audit_integrity": audit.verify_integrity(),
    }


@app.get("/api/consents/{consent_id}/evidence")
def consent_evidence(consent_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM consents WHERE id=?", (consent_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Consent not found")
    audit = AuditLedger()
    audit.events = json.loads(row["audit_json"])
    return {
        "consent_id": consent_id,
        "status": row["status"],
        "propagation": json.loads(row["propagation_json"]),
        "audit_integrity": audit.verify_integrity(),
        "events": audit.events,
    }


@app.post("/api/cases/{case_id}/processors")
def processor_propagation(case_id: str):
    case = get_case(case_id)
    ledger = ledger_from_case(case)
    orchestrator = ProcessorOrchestrator(
        [
            ProcessorNode("Email Provider", "marketing", True, True),
            ProcessorNode("Analytics Provider", "analytics", True, False),
        ],
        ledger,
    )
    results = orchestrator.propagate(case_id, "ERASE", max_retries=2)
    save_audit(case_id, ledger)
    return [result.__dict__ for result in results]


@app.get("/api/cases/{case_id}/evidence")
def evidence(case_id: str):
    case = get_case(case_id)
    ledger = ledger_from_case(case)
    return {
        "case_id": case_id,
        "evidence_type": "PrivacyOps case evidence",
        "status": case["status"],
        "audit_integrity": ledger.verify_integrity(),
        "events": ledger.events,
    }
