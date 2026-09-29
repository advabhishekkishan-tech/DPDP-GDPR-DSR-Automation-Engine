# PrivacyOps DSR Automation Engine — v2

**Techno-legal prototype for operationalising Data Subject Rights (DSR) workflows.**

This version evolves the original simulation into a modular PrivacyOps architecture: **intake → identity assurance → jurisdictional rules → data discovery → retention/legal decision → execution → verification → tamper-evident audit**.

> **Portfolio scope:** This is a safe, in-memory prototype. It does not connect to production databases, CRM systems, cloud storage, or real data-subject records.

## Why v2?

The first version demonstrated the workflow concept but hard-coded a universal 30-day deadline and printed "completed" messages without performing or verifying system actions. v2 separates legal decision-making from technical execution and makes the automation claims demonstrable within mock connectors.

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
    ├── ANONYMIZE / RESTRICT
    └── ESCALATE
    │
    ▼
Mock Connector Execution
    │
    ▼
Post-Execution Verification
    │
    ▼
Hash-Chained Audit Ledger
    │
    ▼
Closure Status
```

## Key capabilities

- **Config-driven deadlines:** GDPR timing is represented as configuration rather than embedded in business logic. DPDP is intentionally left configurable rather than assigned a universal hard-coded DSR deadline.
- **Risk-based identity assurance:** the prototype requires an assurance level and rejects insufficient assurance.
- **Multi-system discovery:** mock connectors represent CRM, database and archive systems without touching real infrastructure.
- **Retention/legal decision layer:** litigation, regulatory and tax tags can preserve data; analytics can trigger anonymisation; other records can be erased.
- **Partial outcomes:** records can be escalated or handled with restriction/anonymisation instead of treating legal hold as a simple global Boolean.
- **Deletion verification:** an erase operation is followed by an explicit check that the record is absent.
- **Tamper-evident audit:** events are hash-chained using SHA-256 and the chain can be integrity-checked.
- **Automated tests + CI:** pytest scenarios run through GitHub Actions.

## Repository

```
src/
  models.py       # Request, record and execution models
  rules.py        # Jurisdiction + retention decision layer
  connectors.py   # Safe in-memory enterprise connectors
  engine.py       # PrivacyOps orchestration
  audit.py        # Hash-chained audit ledger
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
pytest -q
python run_engine.py
```

## Example decision

A request can discover:

- CRM record → anonymise
- archive record under litigation hold → escalate to legal review
- ordinary production record → erase and verify absence

The engine records the **legal decision, technical action and verification evidence** separately.

## PrivacyOps design principle

The goal is not to replace legal judgement. The goal is to make a documented legal decision **operational, repeatable and auditable**.

**Legal decision → Technical control → Evidence**

## Roadmap

- real PostgreSQL/Salesforce/S3 adapters behind the connector interface
- DSR response-package composer with redaction controls
- processor/subprocessor orchestration
- RBAC and approval workflows
- request deduplication and case management
- governed versioning of jurisdictional rules
- DPIA / risk-assessment module
- API layer and web dashboard

## Author

**Abhishek Kishan**  
Advocate | PrivacyOps & Data Protection

