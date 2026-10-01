from datetime import date
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.audit import AuditLedger
from src.connectors import MockSystemConnector
from src.engine import PrivacyOpsEngine
from src.models import DSRRequest, DataRecord, RequestType
from src.rules import RulesEngine

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="PrivacyOps DSR Lab",
    description="Functional web interface for the PrivacyOps DSR prototype.",
    version="0.1.0",
)


class DSRSubmission(BaseModel):
    subject_email: str = Field(min_length=3)
    request_type: RequestType = RequestType.ERASURE
    jurisdiction: str = "GDPR"
    assurance_level: int = Field(default=3, ge=0, le=5)


def build_demo_engine(payload: DSRSubmission) -> PrivacyOpsEngine:
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
        request_id=f"WEB-{date.today().isoformat()}-{payload.subject_email.split('@')[0][:12]}",
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


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "application": "PrivacyOps DSR Lab"}


@app.post("/api/dsr/run")
def run_dsr(payload: DSRSubmission):
    try:
        engine = build_demo_engine(payload)
        result = engine.run(assurance_level=payload.assurance_level)
        return {
            "request_id": engine.request.request_id,
            "status": result["status"],
            "deadline": result["deadline"].isoformat() if result["deadline"] else None,
            "results": result["results"],
            "response_package": result.get("response_package", {}),
            "audit": result["audit"],
            "audit_integrity": engine.audit.verify_integrity(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
