# PrivacyOps DSR & Consent Automation Engine

**Techno-legal prototype for operationalising Data Subject Rights (DSR) and consent-management workflows.**

This project demonstrates a modular PrivacyOps architecture for turning privacy obligations into repeatable technical workflows and evidence.

> **Portfolio scope:** This is a safe, local portfolio prototype. The web application persists demo case and consent metadata in a local SQLite database and uses mock enterprise connectors. It does not connect to production databases, CRM systems, cloud storage, Consent Managers, processors, or real data-subject records. It is not a registered Consent Manager or a production compliance platform.

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

### Governance and processor workflow

```
High-impact Privacy Action
        │
        ▼
  Approval Request
        │
        ▼
   RBAC Check ──fail──> Deny + Audit
        │
        ▼
   Human Approval
        │
        ▼
Controller → Processor
        │
        ├── acknowledgement
        ├── retry handling
        └── verification / pending state
        │
        ▼
   Audit Evidence
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
- **Access response package:** access requests produce a structured package showing source system and returned demo data, with post-export subject matching verification.
- **Deletion verification:** an erase operation is followed by an explicit absence check.
- **Tamper-evident audit:** events are hash-chained using SHA-256 and the chain can be integrity-checked.
- **Duplicate-request detection:** the web application rejects an exact subject/request-type/jurisdiction duplicate with HTTP 409; the standalone registry remains available as a reusable prototype component.
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
- **RBAC and approvals:** high-impact actions are permission-checked and approval decisions are auditable.
- **Processor orchestration:** downstream processors can be propagated to with acknowledgement, retry and failure states.

## Repository

```
src/
  models.py          # DSR, consent, processing-system and execution models
  rules.py           # Jurisdiction + retention decision layer
  connectors.py      # Safe in-memory enterprise connectors
  engine.py          # DSR PrivacyOps orchestration
  consent.py         # Consent lifecycle + withdrawal propagation
  governance.py      # RBAC + approval workflow
  processors.py      # Processor acknowledgement + retry orchestration
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

# Governance + processor orchestration
python run_governance.py
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

The current implementation uses local SQLite for the web application's case/consent metadata, in-memory mock connectors for enterprise records, and simulated processor endpoints. A production architecture would require, among other things:

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


## Functional PrivacyOps application

The repository now includes a local case-management application built on top of the existing DSR, governance, consent, processor and audit components.

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

### What the application does

- Create and persist DSR cases in a local SQLite database.
- Run identity assurance, jurisdiction/rule evaluation, multi-system discovery, record-level legal decisions, technical actions and verification.
- View case history and hash-chained audit evidence.
- Record reviewer approvals through the RBAC/approval layer.
- Simulate controller-to-processor propagation and acknowledgement/retry outcomes.
- Register and withdraw consent records through a simple consent operations screen.
- Expose API endpoints suitable for later integration with real enterprise systems.

### Docker

```bash
docker build -t privacyops-dsr-lab .
docker run -p 8000:8000 privacyops-dsr-lab
```

### Safety / scope

This is a portfolio-grade functional prototype. It uses demo data and mock enterprise connectors; it is not a production privacy platform and must not be connected to live personal data without security, authentication, authorization, privacy, resilience and legal controls appropriate to the deployment.

### Next engineering increments

- Real authentication and role management.
- Durable enterprise database and migrations.
- Connector interface for real databases, CRMs, storage and processor APIs.
- Stronger access-package redaction and authorization.
- Downloadable evidence packages.
- Deployment hardening and observability.


## Public-repository security posture

The repository is intentionally safe to publish as a portfolio project because it uses demo records, mock connectors and local-only storage. The application does **not** contain production credentials or connect to live enterprise systems.

The web UI adds basic browser hardening headers and escapes API-derived values before inserting them into HTML. The application remains deliberately unauthenticated and should be treated as **local/demo software only** unless authentication, authorization, deployment isolation, secure secret handling and operational controls are added.

Before any public deployment, review GitHub Security and quality, secret-scanning alerts, dependency updates, branch protection and the repository's security policy. Never commit API keys, passwords, tokens, private keys, production connection strings or real personal data.

## Validation scenarios

The automated application test suite covers:

- ACCESS DSR response generation and subject matching verification.
- Identity-assurance rejection at insufficient assurance.
- Legal-review approval and unauthorized approval rejection.
- Processor acknowledgement and pending-acknowledgement/retry outcomes.
- Duplicate DSR rejection.
- Consent withdrawal through the actual ConsentPropagationEngine, with persisted audit evidence.
- Hash-chain audit integrity after subsequent governance and processor events.


## Intellectual property and authorship notice

**© 2026 Adv. Abhishek Kishan — All Rights Reserved.**

The PrivacyOps DSR & Consent Automation Engine is an original personal portfolio project by Adv. Abhishek Kishan. The authorship claim covers the original project materials and expression, including but not limited to the user interface, workflow design, architecture, documentation, configuration, original source-code implementation, demonstrations and repository presentation.

The repository is publicly viewable for professional and educational reference. **No licence is granted to copy, redistribute, modify, rebrand, commercially exploit, or create derivative works from the project materials unless expressly authorised in writing by the author.** Third-party libraries and components remain subject to their respective licences.

This notice is an authorship and rights statement; it does not purport to create rights that applicable law does not recognise, and it does not by itself determine the legal scope of protection for abstract ideas or concepts.


## Optional Google sign-in and interaction analytics

The web application can require Google sign-in to distinguish simulator users and maintain an admin-only interaction ledger. The tracker stores the Google account identifier, email/name, timestamps, HTTP method/path and basic account activity. It deliberately does not copy the DSR subject email into the activity ledger.

Set these environment variables in the deployment environment:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SESSION_SECRET` — use a long random value; never commit it
- `REQUIRE_LOGIN=true`
- `ADMIN_EMAIL` — Google account email allowed to view `/api/admin/activity`

Google OAuth must be configured with the deployed callback URL:
`https://<your-domain>/auth/callback`

For the Render deployment, add the variables under the service's Environment settings and use the exact Render service URL in Google's Authorized redirect URIs. The application remains a portfolio prototype; do not enter real DSR subject data.
