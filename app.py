import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from database import connect
from migrations import run_migrations

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
SESSION_SECRET = os.getenv("SESSION_SECRET", "local-development-only-change-me")
REQUIRE_LOGIN = os.getenv("REQUIRE_LOGIN", "false").lower() == "true"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
IS_RENDER = os.getenv("RENDER", "").lower() == "true"
if IS_RENDER and (not os.getenv("SESSION_SECRET") or SESSION_SECRET == "local-development-only-change-me"):
    raise RuntimeError("SESSION_SECRET must be configured with a strong random value in production.")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

app = FastAPI(
    title="PrivacyOps DSR Lab",
    version="1.3.0",
    description="Portfolio PrivacyOps case-management application using demo data and mock enterprise connectors.",
)
@app.on_event("startup")
def initialize_database():
    """Apply pending schema migrations once when the app starts."""
    run_migrations()


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

oauth = OAuth()
if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        client_kwargs={"scope": "openid email profile"},
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

    @field_validator("subject_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("Enter a valid demo email address.")
        return value

    @field_validator("data_categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned or any(len(item) > 100 for item in cleaned):
            raise ValueError("Data categories must be non-empty and concise.")
        return cleaned


def db():
    """Open a connection; schema changes are handled at startup by migrations."""
    return connect()


def get_or_create_session_user(request: Request) -> str:
    user = request.session.get("user")
    if user:
        return user["id"]
    anon_id = request.session.get("anon_id")
    if not anon_id:
        anon_id = f"anon-{uuid4().hex}"
        request.session["anon_id"] = anon_id
        conn = db()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO users (id, provider, email, name, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
            (anon_id, "anonymous", None, "Anonymous visitor", now, now),
        )
        conn.commit()
        conn.close()
    return anon_id


def current_user(request: Request):
    return request.session.get("user")


def require_access(request: Request):
    if REQUIRE_LOGIN and not current_user(request):
        raise HTTPException(401, "Sign-in required for this deployment.")
    return get_or_create_session_user(request)


@app.middleware("http")
async def security_and_activity(request: Request, call_next):
    # SessionMiddleware is downstream of FastAPI's decorator middleware.
    # Resolve the session user only after downstream middleware has populated
    # request.scope["session"] so public requests remain session-safe.
    response = await call_next(request)
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/admin/"):
        # When login is required, do not create anonymous accounts or log
        # unauthenticated API probes as ordinary user activity.
        if not REQUIRE_LOGIN or current_user(request):
            owner_id = get_or_create_session_user(request)
            conn = db()
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE users SET last_seen_at=? WHERE id=?",
                (now, owner_id),
            )
            conn.execute(
                "INSERT INTO activity_events (user_id, method, path, created_at) VALUES (?, ?, ?, ?)",
                (owner_id, request.method, request.url.path, now),
            )
            conn.commit()
            conn.close()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def build_engine(payload: DSRSubmission):
    with open(BASE_DIR / "config" / "rules.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    records = [
        DataRecord("PostgreSQL", "pg-001", {"email": payload.subject_email, "name": "Demo User", "phone": "+91-9000000000"}),
        DataRecord("Salesforce", "crm-001", {"email": payload.subject_email, "marketing": True}, ["analytics"]),
        DataRecord("Archive", "arc-001", {"email": payload.subject_email, "case_ref": "LIT-42"}, ["litigation"]),
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


def save_case(request, result, owner_id):
    conn = db()
    conn.execute(
        """INSERT INTO cases
        (id, subject_email, request_type, jurisdiction, assurance_level, status, deadline,
         results_json, response_json, audit_json, created_at, owner_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            request.request_id, request.subject_email, request.request_type.value,
            request.jurisdiction, request.metadata.get("assurance_level", 2),
            result["status"], result["deadline"].isoformat() if result["deadline"] else None,
            json.dumps(result["results"], default=str), json.dumps(result.get("response_package", {}), default=str),
            json.dumps(result["audit"], default=str), request.created_at.isoformat(), owner_id,
        ),
    )
    conn.commit()
    conn.close()


def get_case(case_id, owner_id):
    conn = db()
    row = conn.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, owner_id)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Case not found")
    return dict(row)


def ledger_from_case(case):
    ledger = AuditLedger()
    ledger.events = json.loads(case["audit_json"])
    return ledger


def save_audit(case_id, owner_id, ledger):
    conn = db()
    conn.execute("UPDATE cases SET audit_json=? WHERE id=? AND owner_id=?", (json.dumps(ledger.events, default=str), case_id, owner_id))
    conn.commit()
    conn.close()


def consent_from_row(row) -> ConsentRecord:
    return ConsentRecord(
        consent_id=row["id"], subject_email=row["subject_email"], fiduciary="Example Corp",
        purpose=row["purpose"], data_categories=json.loads(row["data_categories"]),
        status=ConsentStatus(row["status"]),
        granted_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc),
        withdrawn_at=(datetime.fromisoformat(row["withdrawn_at"]).replace(tzinfo=timezone.utc) if row["withdrawn_at"] else None),
    )


def consent_systems(consent: ConsentRecord) -> list[ProcessingSystem]:
    return [
        ProcessingSystem("CRM", consent.purpose, consent.data_categories),
        ProcessingSystem("Email Provider", consent.purpose, consent.data_categories, processor="Mail Processor"),
        ProcessingSystem("Analytics", "product-analytics", consent.data_categories, processor="Analytics Provider"),
    ]


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return HTMLResponse("""<!doctype html><html><head><meta charset="utf-8"><title>Privacy Notice - PrivacyOps DSR Lab</title>
<style>body{font:16px system-ui;max-width:850px;margin:40px auto;padding:0 20px;line-height:1.6;color:#172033}h1{line-height:1.2}code{background:#f1f5f9;padding:2px 5px}</style></head><body>
<h1>Privacy Notice — PrivacyOps DSR Lab</h1>
<p><strong>Controller:</strong> Adv. Abhishek Kishan, for this portfolio demonstration.</p>
<p>This simulator is a public proof-of-concept using synthetic/demo data. Do not enter real personal data or real data-subject requests.</p>
<h2>What may be collected</h2><p>The application may record account/session identifiers, optional Google account name/email when Google sign-in is enabled, timestamps, HTTP method and API path for basic usage analytics. DSR and consent records entered into the simulator are stored as demo application data.</p>
<h2>Why</h2><p>To provide the simulator, prevent cross-user access to case records, maintain auditability, understand feature usage and improve the portfolio demonstration.</p>
<h2>Third parties</h2><p>If Google sign-in is enabled, Google authentication is used for account authentication. The deployment may also use infrastructure providers such as Render to host the application.</p>
<h2>Important</h2><p>This is not a production privacy-management platform. Do not submit real customer, employee, financial, health, identity or other sensitive information.</p>
<h2>Questions</h2><p>For privacy questions concerning this demonstration, contact the project author through the contact details published with the project.</p>
<p><a href="/">Return to simulator</a></p></body></html>""")


@app.get("/health")
def health():
    return {"status": "ok", "application": "PrivacyOps DSR Lab", "version": "1.3.0"}


@app.get("/api/me")
def me(request: Request):
    user = current_user(request)
    owner_id = None if REQUIRE_LOGIN and not user else get_or_create_session_user(request)
    return {
        "authenticated": bool(user),
        "user": user,
        "tracking_id": owner_id if not user and not REQUIRE_LOGIN else None,
        "admin": bool(user and ADMIN_EMAIL and user.get("email", "").lower() == ADMIN_EMAIL),
        "login_available": bool(getattr(oauth, "google", None)),
        "login_required": REQUIRE_LOGIN,
    }


@app.get("/auth/login")
async def auth_login(request: Request):
    if not getattr(oauth, "google", None):
        raise HTTPException(503, "Google sign-in is not configured.")
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    if not getattr(oauth, "google", None):
        raise HTTPException(503, "Google sign-in is not configured.")
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)
    user_id = f"google:{userinfo['sub']}"
    now = datetime.now(timezone.utc).isoformat()
    user = {"id": user_id, "email": userinfo.get("email", ""), "name": userinfo.get("name", "")}
    anonymous_id = request.session.get("anon_id")
    request.session["user"] = user
    conn = db()
    if anonymous_id:
        conn.execute("UPDATE cases SET owner_id=? WHERE owner_id=?", (user_id, anonymous_id))
        conn.execute("UPDATE consents SET owner_id=? WHERE owner_id=?", (user_id, anonymous_id))
        conn.execute("UPDATE activity_events SET user_id=? WHERE user_id=?", (user_id, anonymous_id))
        conn.execute("DELETE FROM users WHERE id=? AND provider='anonymous'", (anonymous_id,))
        request.session.pop("anon_id", None)
    conn.execute(
        """INSERT INTO users (id, provider, email, name, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET email=excluded.email, name=excluded.name, last_seen_at=excluded.last_seen_at""",
        (user_id, "google", user["email"], user["name"], now, now),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)


@app.post("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/admin/activity")
def admin_activity(request: Request):
    user = current_user(request)
    if not user or not ADMIN_EMAIL or user.get("email", "").lower() != ADMIN_EMAIL:
        raise HTTPException(403, "Admin access required.")
    conn = db()
    users = conn.execute(
        "SELECT id, provider, email, name, created_at, last_seen_at FROM users ORDER BY last_seen_at DESC LIMIT 500"
    ).fetchall()
    events = conn.execute(
        "SELECT user_id, method, path, created_at FROM activity_events ORDER BY id DESC LIMIT 500"
    ).fetchall()
    conn.close()
    return {"users": [dict(x) for x in users], "events": [dict(x) for x in events]}


@app.get("/api/cases")
def list_cases(request: Request):
    owner_id = require_access(request)
    conn = db()
    rows = conn.execute(
        "SELECT id, request_type, jurisdiction, status, created_at FROM cases WHERE owner_id=? ORDER BY created_at DESC",
        (owner_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str, request: Request):
    owner_id = require_access(request)
    case = get_case(case_id, owner_id)
    case["results"] = json.loads(case["results_json"])
    case["response_package"] = json.loads(case["response_json"])
    case["audit"] = json.loads(case["audit_json"])
    case["audit_integrity"] = ledger_from_case(case).verify_integrity()
    del case["results_json"], case["response_json"], case["audit_json"], case["subject_email"]
    return case


@app.post("/api/cases")
def create_case(payload: DSRSubmission, request: Request):
    owner_id = require_access(request)
    conn = db()
    existing = conn.execute(
        "SELECT id FROM cases WHERE owner_id=? AND lower(subject_email)=lower(?) AND request_type=? AND jurisdiction=? LIMIT 1",
        (owner_id, payload.subject_email, payload.request_type.value, payload.jurisdiction),
    ).fetchone()
    conn.close()
    if existing:
        raise HTTPException(409, detail=f"Duplicate DSR detected. Existing case: {existing['id']}")
    engine = build_engine(payload)
    engine.request.metadata["assurance_level"] = payload.assurance_level
    result = engine.run(assurance_level=payload.assurance_level)
    save_case(engine.request, result, owner_id)
    return case_detail(engine.request.request_id, request)


@app.post("/api/cases/{case_id}/approvals")
def approval(case_id: str, payload: ApprovalSubmission, request: Request):
    owner_id = require_access(request)
    case = get_case(case_id, owner_id)
    ledger = ledger_from_case(case)
    governance = GovernanceEngine(ledger)
    approval_id = f"APR-{uuid4().hex[:8]}"
    approval_request = ApprovalRequest(approval_id, case_id, payload.action, ActorRole.PRIVACY_ANALYST, payload.reason)
    governance.request(approval_request)
    decision = governance.decide(approval_request, payload.role, payload.approved, payload.reason)
    if payload.action == "LEGAL_REVIEW" and decision.approved:
        conn = db()
        conn.execute(
            "UPDATE cases SET status=? WHERE id=? AND owner_id=? AND status=?",
            ("APPROVED_FOR_EXECUTION", case_id, owner_id, "ESCALATED"),
        )
        conn.commit()
        conn.close()
        ledger.append(
            case_id,
            "EXECUTION_AUTHORIZED",
            {"approval_id": decision.approval_id, "action": "LEGAL_REVIEW"},
        )
    save_audit(case_id, owner_id, ledger)
    return decision.__dict__


@app.get("/api/consents")
def list_consents(request: Request):
    owner_id = require_access(request)
    conn = db()
    rows = conn.execute(
        "SELECT id, purpose, data_categories, status, created_at, withdrawn_at, propagation_json FROM consents WHERE owner_id=? ORDER BY created_at DESC",
        (owner_id,),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["data_categories"] = json.loads(item["data_categories"])
        item["propagation"] = json.loads(item.pop("propagation_json") or "[]")
        result.append(item)
    return result


@app.post("/api/consents")
def create_consent(payload: ConsentSubmission, request: Request):
    owner_id = require_access(request)
    consent_id = f"CONS-{uuid4().hex[:8]}"
    audit = AuditLedger()
    consent = ConsentRecord(
        consent_id=consent_id, subject_email=payload.subject_email, fiduciary="Example Corp",
        purpose=payload.purpose, data_categories=payload.data_categories, granted_at=datetime.now(timezone.utc),
    )
    ConsentLedger().register(consent, audit)
    conn = db()
    conn.execute(
        """INSERT INTO consents
        (id, subject_email, purpose, data_categories, status, created_at, withdrawn_at, audit_json, propagation_json, owner_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (consent_id, payload.subject_email, payload.purpose, json.dumps(payload.data_categories),
         ConsentStatus.ACTIVE.value, datetime.now(timezone.utc).isoformat(), None, json.dumps(audit.events), "[]", owner_id),
    )
    conn.commit()
    conn.close()
    return {"consent_id": consent_id, "status": "ACTIVE", "audit_integrity": audit.verify_integrity()}


@app.post("/api/consents/{consent_id}/withdraw")
def withdraw_consent(consent_id: str, request: Request):
    owner_id = require_access(request)
    conn = db()
    row = conn.execute("SELECT * FROM consents WHERE id=? AND owner_id=?", (consent_id, owner_id)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Consent not found")
    if row["status"] == ConsentStatus.WITHDRAWN.value:
        audit = AuditLedger()
        audit.events = json.loads(row["audit_json"])
        return {"consent_id": consent_id, "status": ConsentStatus.WITHDRAWN.value,
                "propagation": json.loads(row["propagation_json"]), "audit_integrity": audit.verify_integrity()}
    consent = consent_from_row(row)
    ledger = ConsentLedger()
    ledger.records[consent.consent_id] = consent
    audit = AuditLedger()
    audit.events = json.loads(row["audit_json"])
    results = ConsentPropagationEngine(ledger, consent_systems(consent), audit).propagate_withdrawal(consent_id)
    conn = db()
    conn.execute(
        "UPDATE consents SET status=?, withdrawn_at=?, audit_json=?, propagation_json=? WHERE id=? AND owner_id=?",
        (ConsentStatus.WITHDRAWN.value, datetime.now(timezone.utc).isoformat(), json.dumps(audit.events, default=str),
         json.dumps([result.__dict__ for result in results], default=str), consent_id, owner_id),
    )
    conn.commit()
    conn.close()
    return {"consent_id": consent_id, "status": ConsentStatus.WITHDRAWN.value,
            "propagation": [result.__dict__ for result in results], "audit_integrity": audit.verify_integrity()}


@app.get("/api/consents/{consent_id}/evidence")
def consent_evidence(consent_id: str, request: Request):
    owner_id = require_access(request)
    conn = db()
    row = conn.execute("SELECT * FROM consents WHERE id=? AND owner_id=?", (consent_id, owner_id)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Consent not found")
    audit = AuditLedger()
    audit.events = json.loads(row["audit_json"])
    return {"consent_id": consent_id, "status": row["status"], "propagation": json.loads(row["propagation_json"]),
            "audit_integrity": audit.verify_integrity(), "events": audit.events}


@app.post("/api/cases/{case_id}/processors")
def processor_propagation(case_id: str, request: Request):
    owner_id = require_access(request)
    case = get_case(case_id, owner_id)
    ledger = ledger_from_case(case)
    orchestrator = ProcessorOrchestrator(
        [ProcessorNode("Email Provider", "marketing", True, True), ProcessorNode("Analytics Provider", "analytics", True, False)],
        ledger,
    )
    request_type = case["request_type"]
    status = case["status"]
    if request_type == RequestType.ACCESS.value:
        action = "EXPORT"
    elif request_type == RequestType.ERASURE.value:
        action = "ERASE"
    else:
        raise HTTPException(422, "Unsupported DSR processor action.")
    if status not in {"FULFILLED", "PARTIAL", "APPROVED_FOR_EXECUTION"}:
        raise HTTPException(409, f"Processor propagation is not available for case status {status}.")
    results = orchestrator.propagate(case_id, action, max_retries=2)
    save_audit(case_id, owner_id, ledger)
    return [result.__dict__ for result in results]


@app.get("/api/cases/{case_id}/evidence")
def evidence(case_id: str, request: Request):
    owner_id = require_access(request)
    case = get_case(case_id, owner_id)
    ledger = ledger_from_case(case)
    return {"case_id": case_id, "evidence_type": "PrivacyOps case evidence", "status": case["status"],
            "audit_integrity": ledger.verify_integrity(), "events": ledger.events}
