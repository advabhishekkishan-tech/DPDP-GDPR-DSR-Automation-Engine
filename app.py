import json
import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.audit import AuditLedger
from src.connectors import MockSystemConnector
from src.engine import PrivacyOpsEngine
from src.governance import ApprovalRequest, GovernanceEngine
from src.models import ActorRole, ConsentRecord, ProcessingSystem, DSRRequest, DataRecord, RequestType, ConsentStatus
from src.processors import ProcessorNode, ProcessorOrchestrator
from src.rules import RulesEngine

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "privacyops.db"

app = FastAPI(title="PrivacyOps DSR Lab", version="1.0.0",
              description="Local PrivacyOps case-management application using the repository's DSR engine.")


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
    conn.commit()
    return conn


class DSRSubmission(BaseModel):
    subject_email: str = Field(min_length=3)
    request_type: RequestType = RequestType.ERASURE
    jurisdiction: str = "GDPR"
    assurance_level: int = Field(default=3, ge=0, le=5)


class ApprovalSubmission(BaseModel):
    action: str
    role: ActorRole
    approved: bool
    reason: str = ""


class ConsentSubmission(BaseModel):
    subject_email: str
    purpose: str
    data_categories: list[str]


def build_engine(payload: DSRSubmission):
    with open(BASE_DIR / "config" / "rules.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    records = [
        DataRecord("PostgreSQL", "pg-001",
                   {"email": payload.subject_email, "name": "Demo User", "phone": "+91-9000000000"}),
        DataRecord("Salesforce", "crm-001",
                   {"email": payload.subject_email, "marketing": True}, ["analytics"]),
        DataRecord("Archive", "arc-001",
                   {"email": payload.subject_email, "case_ref": "LIT-42"}, ["litigation"]),
    ]
    request = DSRRequest(
        request_id=f"WEB-{date.today().isoformat()}-{uuid4().hex[:8]}",
        subject_email=payload.subject_email, request_type=payload.request_type,
        jurisdiction=payload.jurisdiction, created_at=date.today())
    return PrivacyOpsEngine(
        request, RulesEngine(config),
        [MockSystemConnector("PostgreSQL", [records[0]]),
         MockSystemConnector("Salesforce", [records[1]]),
         MockSystemConnector("Archive", [records[2]])],
        AuditLedger())


def save_case(request, result):
    conn = db()
    conn.execute("""INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
        request.request_id, request.subject_email, request.request_type.value,
        request.jurisdiction, request.metadata.get("assurance_level", 2), result["status"],
        result["deadline"].isoformat() if result["deadline"] else None,
        json.dumps(result["results"], default=str), json.dumps(result.get("response_package", {}), default=str),
        json.dumps(result["audit"], default=str), request.created_at.isoformat()))
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
    conn.execute("UPDATE cases SET audit_json=? WHERE id=?", (json.dumps(ledger.events, default=str), case_id))
    conn.commit()
    conn.close()


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "application": "PrivacyOps DSR Lab", "version": "1.0.0"}


@app.get("/api/cases")
def list_cases():
    conn = db()
    rows = conn.execute("SELECT id, subject_email, request_type, jurisdiction, status, created_at FROM cases ORDER BY created_at DESC").fetchall()
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
    request = ApprovalRequest(approval_id, case_id, payload.action, ActorRole.PRIVACY_ANALYST, payload.reason)
    governance.request(request)
    decision = governance.decide(request, payload.role, payload.approved, payload.reason)
    save_audit(case_id, ledger)
    return decision.__dict__


@app.get("/api/consents")
def list_consents():
    conn = db()
    rows = conn.execute("SELECT * FROM consents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/consents")
def create_consent(payload: ConsentSubmission):
    consent_id = f"CONS-{uuid4().hex[:8]}"
    conn = db()
    conn.execute("INSERT INTO consents VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (consent_id, payload.subject_email, payload.purpose,
                  json.dumps(payload.data_categories), ConsentStatus.ACTIVE.value,
                  date.today().isoformat(), None))
    conn.commit()
    conn.close()
    return {"consent_id": consent_id, "status": "ACTIVE"}


@app.post("/api/consents/{consent_id}/withdraw")
def withdraw_consent(consent_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM consents WHERE id=?", (consent_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Consent not found")
    conn.execute("UPDATE consents SET status=?, withdrawn_at=? WHERE id=?",
                 ("WITHDRAWN", date.today().isoformat(), consent_id))
    conn.commit()
    conn.close()
    return {"consent_id": consent_id, "status": "WITHDRAWN", "propagation": [
        {"system": "CRM", "action": "WITHDRAW_CONSENT", "verified": True},
        {"system": "Email Provider", "action": "WITHDRAW_CONSENT", "verified": True},
    ]}


@app.post("/api/cases/{case_id}/processors")
def processor_propagation(case_id: str):
    case = get_case(case_id)
    ledger = ledger_from_case(case)
    orchestrator = ProcessorOrchestrator([
        ProcessorNode("Email Provider", "marketing", True, True),
        ProcessorNode("Analytics Provider", "analytics", True, False),
    ], ledger)
    results = orchestrator.propagate(case_id, "ERASE", max_retries=2)
    save_audit(case_id, ledger)
    return [r.__dict__ for r in results]


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
