import os

os.environ["COOKIE_SECURE"] = "false"
os.environ["REQUIRE_LOGIN"] = "false"

from fastapi.testclient import TestClient

import app


def test_public_session_gets_tracking_identity():
    with TestClient(app.app) as client:
        response = client.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["tracking_id"].startswith("anon-")


def test_privacy_notice_is_public():
    with TestClient(app.app) as client:
        response = client.get("/privacy")
        assert response.status_code == 200
        assert "Privacy Notice" in response.text


def test_case_detail_does_not_return_subject_email():
    with TestClient(app.app) as client:
        created = client.post(
            "/api/cases",
            json={
                "subject_email": "privacy-test@example.com",
                "request_type": "ACCESS",
                "jurisdiction": "GDPR",
                "assurance_level": 3,
            },
        )
        assert created.status_code == 200
        case_id = created.json()["id"]

        detail = client.get(f"/api/cases/{case_id}")
        assert detail.status_code == 200
        assert "subject_email" not in detail.json()


def test_another_session_cannot_read_first_session_case():
    with TestClient(app.app) as first:
        created = first.post(
            "/api/cases",
            json={
                "subject_email": "isolation-test@example.com",
                "request_type": "ERASURE",
                "jurisdiction": "GDPR",
                "assurance_level": 3,
            },
        )
        assert created.status_code == 200
        case_id = created.json()["id"]

    with TestClient(app.app) as second:
        response = second.get(f"/api/cases/{case_id}")
        assert response.status_code == 404
