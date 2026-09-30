# PrivacyOps DSR & Consent Automation Engine

**Techno-legal prototype for operationalising Data Subject Rights (DSR) and consent-management workflows.**

This project demonstrates a modular PrivacyOps architecture for turning privacy obligations into repeatable technical workflows and evidence.

> **Portfolio scope:** This is a safe, in-memory prototype. It does not connect to production databases, CRM systems, cloud storage, Consent Managers, processors, or real data-subject records. It is not a registered Consent Manager or a production compliance platform.

## Architecture

### DSR workflow

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

### Consent lifecycle workflow

```
Consent Grant
    │
    ▼
Consent Ledger
    │
    ├── REVIEW
    │
    └── WITHDRAW
          │
          ▼
    Purpose / Data-Category Matching
          │
          ▼
    Downstream Processing Systems
          │
          ├── Fiduciary system
          ├── Processor
          └── Other processing system
          │
          ▼
    Withdrawal Propagation
          │
          ▼
    Post-Propagation Verification
          │
          ▼
    Hash-Chained Audit Evidence
```

## Key capabilities

### DSR / PrivacyOps

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

### Consent Management prototype

- **Consent lifecycle:** grant, review and withdrawal are represented as explicit state changes.
- **Consent ledger:** consent state and lifecycle history are maintained separately from processing systems.
- **Purpose mapping:** withdrawal is propagated only to systems whose processing purpose and data categories match the consent.
- **Processor visibility:** downstream systems can identify an associated processor.
- **Withdrawal propagation:** matching consent-dependent systems are marked inactive when consent is withdrawn.
- **Processing-basis distinction:** systems marked as not consent-dependent are not automatically disabled by a consent withdrawal.
- **Post-propagation verification:** each affected system produces a verification result.
- **Consent-specific audit evidence:** grant, review, withdrawal, propagation and verification events are written to the hash-chained audit ledger.

## Repository

```
src/
  models.py          # DSR, consent, processing-system and execution models
  rules.py           # Jurisdiction + retention decision layer
  connectors.py      # Safe in-memory enterprise connectors
  engine.py          # DSR PrivacyOps orchestration
  consent.py         # Consent lifecycle + withdrawal propagation
  audit.py            # Hash-chained audit ledger
  case_management.py # Duplicate-request detection
config/
  rules.yaml
  scenarios.yaml
tests/
  test_engine.py
  test_consent.py
run_engine.py
run_consent.py
.github/workflows/run_dsr.yml
```

## Run locally

```bash
pip install -r requirements.txt

# DSR workflow
python -m pytest -q
python run_engine.py

# Consent workflow
python run_consent.py
```

## Example consent scenario

A consent record may authorise processing for:

- purpose → marketing
- categories → email, phone
- fiduciary → Example Corp

The prototype then models downstream systems:

- CRM → marketing
- Email Provider → marketing, processor
- Analytics → product analytics

When the consent is withdrawn, only matching consent-dependent systems are targeted. Each propagation step is verified and written to the audit ledger.

The important design distinction is:

**Consent state ≠ processing purpose ≠ technical system state**

A consent withdrawal therefore becomes an operational event that must be propagated and evidenced rather than a single boolean update.

## PrivacyOps design principle

The project is designed around:

**Legal / privacy decision → Technical control → Verification → Evidence**

The goal is not to replace legal judgement. The goal is to make a documented privacy decision **operational, repeatable and auditable**.

## Prototype boundaries

This repository deliberately does **not** claim production compliance or regulatory registration.

The current implementation uses in-memory state and simulated connectors. A production architecture would require, among other things:

- authenticated APIs and real system adapters
- persistent case and consent storage
- strong identity and access controls
- processor/subprocessor acknowledgement and retry handling
- secure consent and DSR response delivery
- access-package redaction and third-party data handling
- governed policy/rule versioning
- durable and access-controlled audit storage
- monitoring, incident handling and operational controls
- regulatory governance appropriate to the deployment context

## Roadmap

- real PostgreSQL/Salesforce/S3 adapters behind the connector interface
- stronger access-package redaction and third-party data handling
- processor/subprocessor orchestration with acknowledgements and retries
- RBAC and approval workflows
- persistent case and consent management
- governed versioning and approval of jurisdictional rules
- DPIA / risk-assessment module
- API layer and web dashboard
- consent receipts and secure consent history export

## Author

**Abhishek Kishan**  
Advocate | PrivacyOps & Data Protection
