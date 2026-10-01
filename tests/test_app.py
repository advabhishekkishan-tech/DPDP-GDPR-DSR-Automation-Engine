from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_run_erasure_workflow():
    response = client.post(
        "/api/dsr/run",
        json={
            "subject_email": "user@example.com",
            "request_type": "ERASURE",
            "jurisdiction": "GDPR",
            "assurance_level": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ESCALATED"
    assert data["audit_integrity"] is True
    assert any(item["action"] == "ERASE" for item in data["results"])
    assert any(item["action"] == "ANONYMIZE" for item in data["results"])
    assert any(item["action"] == "LEGAL_REVIEW" for item in data["results"])


def test_identity_failure_stops_execution():
    response = client.post(
        "/api/dsr/run",
        json={
            "subject_email": "user@example.com",
            "request_type": "ERASURE",
            "jurisdiction": "GDPR",
            "assurance_level": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED_UNVERIFIED"
