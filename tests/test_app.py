from uuid import uuid4

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def email():
    return f"{uuid4().hex[:10]}@example.com"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_access_dsr_produces_verified_response_package():
    subject = email()
    r = client.post(
        "/api/cases",
        json={
            "subject_email": subject,
            "request_type": "ACCESS",
            "jurisdiction": "GDPR",
            "assurance_level": 3,
        },
    )
    assert r.status_code == 200
    case = r.json()
    assert case["status"] == "FULFILLED"
    assert case["audit_integrity"] is True
    assert case["response_package"]["data"]
    assert all(
        item["data"].get("email") == subject
        for item in case["response_package"]["data"]
    )


def test_identity_failure():
    r = client.post(
        "/api/cases",
        json={
            "subject_email": email(),
            "request_type": "ERASURE",
            "jurisdiction": "GDPR",
            "assurance_level": 1,
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED_UNVERIFIED"


def test_legal_review_approval_and_rejection_are_recorded():
    subject = email()
    r = client.post(
        "/api/cases",
        json={
            "subject_email": subject,
            "request_type": "ERASURE",
            "jurisdiction": "GDPR",
            "assurance_level": 3,
        },
    )
    assert r.status_code == 200
    case_id = r.json()["id"]

    rejected = client.post(
        f"/api/cases/{case_id}/approvals",
        json={
            "action": "LEGAL_REVIEW",
            "role": "PRIVACY_ANALYST",
            "approved": True,
            "reason": "Attempted approval by analyst",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["approved"] is False

    approved = client.post(
        f"/api/cases/{case_id}/approvals",
        json={
            "action": "LEGAL_REVIEW",
            "role": "LEGAL_REVIEWER",
            "approved": True,
            "reason": "Reviewed retention conflict",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["approved"] is True

    evidence = client.get(f"/api/cases/{case_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["audit_integrity"] is True
    events = [item["event"] for item in evidence.json()["events"]]
    assert "APPROVAL_REQUESTED" in events
    assert "APPROVAL_DECISION" in events


def test_processor_propagation_exposes_ack_and_failure_states():
    r = client.post(
        "/api/cases",
        json={
            "subject_email": email(),
            "request_type": "ERASURE",
            "jurisdiction": "GDPR",
            "assurance_level": 3,
        },
    )
    case_id = r.json()["id"]
    propagated = client.post(f"/api/cases/{case_id}/processors")
    assert propagated.status_code == 200
    results = propagated.json()
    assert len(results) == 2
    assert any(item["verified"] is True for item in results)
    assert any(item["verified"] is False for item in results)

    evidence = client.get(f"/api/cases/{case_id}/evidence").json()
    assert evidence["audit_integrity"] is True
    assert any(
        item["event"] == "PROCESSOR_PROPAGATION_RESULT"
        for item in evidence["events"]
    )


def test_duplicate_dsr_is_rejected():
    subject = email()
    payload = {
        "subject_email": subject,
        "request_type": "ERASURE",
        "jurisdiction": "GDPR",
        "assurance_level": 3,
    }
    first = client.post("/api/cases", json=payload)
    assert first.status_code == 200
    second = client.post("/api/cases", json=payload)
    assert second.status_code == 409
    assert "Duplicate DSR detected" in second.json()["detail"]


def test_consent_withdrawal_uses_propagation_engine_and_persists_evidence():
    subject = email()
    r = client.post(
        "/api/consents",
        json={
            "subject_email": subject,
            "purpose": "marketing",
            "data_categories": ["email", "phone"],
        },
    )
    assert r.status_code == 200
    assert r.json()["audit_integrity"] is True
    consent_id = r.json()["consent_id"]

    withdrawn = client.post(f"/api/consents/{consent_id}/withdraw")
    assert withdrawn.status_code == 200
    body = withdrawn.json()
    assert body["status"] == "WITHDRAWN"
    assert body["audit_integrity"] is True
    assert {item["system"] for item in body["propagation"]} == {
        "CRM",
        "Email Provider",
    }
    assert all(item["verified"] for item in body["propagation"])

    evidence = client.get(f"/api/consents/{consent_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["audit_integrity"] is True
    assert any(
        item["event"] == "CONSENT_PROPAGATION"
        for item in evidence.json()["events"]
    )

def test_processor_propagation_uses_case_request_action():
    r = client.post("/api/cases", json={"subject_email": email(), "request_type": "ERASURE", "jurisdiction": "GDPR", "assurance_level": 3})
    assert r.status_code == 200
    results = client.post(f"/api/cases/{r.json()['id']}/processors")
    assert results.status_code == 200
    assert {item["action"] for item in results.json()} == {"ERASE"}


def test_access_case_processor_action_is_export():
    r = client.post("/api/cases", json={"subject_email": email(), "request_type": "ACCESS", "jurisdiction": "GDPR", "assurance_level": 3})
    assert r.status_code == 200
    results = client.post(f"/api/cases/{r.json()['id']}/processors")
    assert results.status_code == 200
    assert {item["action"] for item in results.json()} == {"EXPORT"}


def test_processor_propagation_blocked_for_rejected_case():
    r = client.post("/api/cases", json={"subject_email": email(), "request_type": "ERASURE", "jurisdiction": "GDPR", "assurance_level": 1})
    assert r.status_code == 200
    assert client.post(f"/api/cases/{r.json()['id']}/processors").status_code == 409


def test_audit_tampering_is_detected():
    import json
    import app as app_module
    r = client.post("/api/cases", json={"subject_email": email(), "request_type": "ERASURE", "jurisdiction": "GDPR", "assurance_level": 3})
    assert r.status_code == 200
    case_id = r.json()["id"]
    conn = app_module.db()
    row = conn.execute("SELECT audit_json FROM cases WHERE id=?", (case_id,)).fetchone()
    events = json.loads(row["audit_json"])
    events[0]["event"] = "TAMPERED"
    conn.execute("UPDATE cases SET audit_json=? WHERE id=?", (json.dumps(events), case_id))
    conn.commit()
    conn.close()
    assert client.get(f"/api/cases/{case_id}/evidence").json()["audit_integrity"] is False



def test_approved_legal_review_unlocks_escalated_case_for_execution():
    subject = email()
    created = client.post("/api/cases", json={"subject_email": subject, "request_type": "ERASURE", "jurisdiction": "GDPR", "assurance_level": 3})
    assert created.status_code == 200
    case_id = created.json()["id"]
    assert created.json()["status"] == "ESCALATED"

    denied = client.post(f"/api/cases/{case_id}/approvals", json={"action": "LEGAL_REVIEW", "role": "PRIVACY_ANALYST", "approved": True, "reason": "Not authorised"})
    assert denied.status_code == 200
    assert denied.json()["approved"] is False

    approved = client.post(f"/api/cases/{case_id}/approvals", json={"action": "LEGAL_REVIEW", "role": "LEGAL_REVIEWER", "approved": True, "reason": "Retention conflict reviewed"})
    assert approved.status_code == 200
    assert approved.json()["approved"] is True

    detail = client.get(f"/api/cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "APPROVED_FOR_EXECUTION"
    propagated = client.post(f"/api/cases/{case_id}/processors")
    assert propagated.status_code == 200
    assert {item["action"] for item in propagated.json()} == {"ERASE"}
