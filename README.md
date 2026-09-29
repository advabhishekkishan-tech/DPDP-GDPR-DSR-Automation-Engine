# PrivacyOps DSR Automation Engine

**Techno-legal prototype for operationalising Data Subject Rights (DSR) workflows.**

This project demonstrates a modular PrivacyOps architecture: **intake → identity assurance → jurisdictional rules → data discovery → retention/legal decision → execution → verification → evidence → closure**.

> **Portfolio scope:** This is a safe, in-memory prototype. It does not connect to production databases, CRM systems, cloud storage, or real data-subject records.

## Architecture

```
DSR Request
    │
    ▼
Identity Assurance ──fail──> Reject + Audit
    │
    ▼
Jurisdiction / Rules Engine
    │
    ▼
Multi-System Discovery
    │
    ▼
Retention & Legal Decision
    ├── ERASE
    ├── ANONYMIZE
    ├── RESTRICT
    └── ESCALATE
    │
    ▼
Mock Connector Execution
    │
    ▼
Post-Execution Verification
    │
    ▼
Response / Evidence Package
    │
    ▼
Hash-Chained Audit Ledger
    │
    ▼
Closure Status
```

## Key capabilities

- **Config-driven deadlines:** jurisdictional timing is represented as configuration rather than embedded in business logic.
- **Risk-based identity assurance:** insufficient assurance prevents fulfillment.
- **Multi-system discovery:** mock connectors represent database, CRM and archive systems without touching real infrastructure.
- **Record-level retention decisions:** preservation, restriction, anonymisation and erasure can be decided per record.
- **Real partial execution:** anonymisation and processing restriction mutate the mock system and are independently verified.
- **Access response package:** access requests produce a structured package showing source system and returned data.
- **Deletion verification:** an erase operation is followed by an explicit absence check.
- **Tamper-evident audit:** events are hash-chained using SHA-256 and the chain can be integrity-checked.
- **Duplicate-request detection:** a lightweight case registry prevents the same subject/request-type combination from being registered twice.
- **Automated tests + CI:** pytest scenarios run through GitHub Actions.

## Repository

```
src/
  models.py          # Request, record, execution and role models
  rules.py           # Jurisdiction + retention decision layer
  connectors.py      # Safe in-memory enterprise connectors
  engine.py          # PrivacyOps orchestration
  audit.py           # Hash-chained audit ledger
  case_management.py # Duplicate-request detection
config/
  rules.yaml
  scenarios.yaml
tests/
  test_engine.py
run_engine.py
.github/workflows/run_dsr.yml
```

## Run locally

```bash
pip install -r requirements.txt
python -m pytest -q
python run_engine.py
```

## Example decision

A single request can discover:

- ordinary production record → erase + verify absence
- analytics record → anonymise + verify transformation
- security-investigation record → restrict processing + verify restriction
- archive record under litigation retention → escalate for legal review

The engine records the **legal decision, technical action and verification evidence** separately.

## PrivacyOps design principle

The goal is not to replace legal judgement. The goal is to make a documented legal decision **operational, repeatable and auditable**.

**Legal decision → Technical control → Evidence**

## Roadmap

- real PostgreSQL/Salesforce/S3 adapters behind the connector interface
- stronger access-package redaction and third-party data handling
- processor/subprocessor orchestration
- RBAC and approval workflows
- persistent case management and duplicate detection
- governed versioning and approval of jurisdictional rules
- DPIA / risk-assessment module
- API layer and web dashboard

## Author

**Abhishek Kishan**  
Advocate | PrivacyOps & Data Protection
