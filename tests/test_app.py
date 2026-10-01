from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_create_and_read_case():
    r = client.post("/api/cases", json={
        "subject_email": "test@example.com", "request_type": "ERASURE",
        "jurisdiction": "GDPR", "assurance_level": 3
    })
    assert r.status_code == 200
    case = r.json()
    assert case["audit_integrity"] is True
    assert any(x["action"] == "ERASE" for x in case["results"])
    assert any(x["action"] == "ANONYMIZE" for x in case["results"])
    assert any(x["action"] == "LEGAL_REVIEW" for x in case["results"])

def test_identity_failure():
    r = client.post("/api/cases", json={
        "subject_email": "weak@example.com", "request_type": "ERASURE",
        "jurisdiction": "GDPR", "assurance_level": 1
    })
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED_UNVERIFIED"

def test_consent_lifecycle():
    r = client.post("/api/consents", json={
        "subject_email": "consent@example.com", "purpose": "marketing",
        "data_categories": ["email", "phone"]
    })
    assert r.status_code == 200
    cid = r.json()["consent_id"]
    r = client.post(f"/api/consents/{cid}/withdraw")
    assert r.status_code == 200
    assert r.json()["status"] == "WITHDRAWN"
