[![Run DSR Engine Check](https://github.com/advabhishekkishan-tech/DPDP-GDPR-DSR-Automation-Engine/actions/workflows/run_dsr.yml/badge.svg)](https://github.com/advabhishekkishan-tech/DPDP-GDPR-DSR-Automation-Engine/actions/workflows/run_dsr.yml)
# DPDP-GDPR-DSR-Automation-Engine
Open-source Techno-Legal workflow engine for automating Data Subject Rights (Access &amp; Erasure) under the DPDP Act 2023 &amp; GDPR.
# 🛡️ Techno-Legal DSR Automation Engine
*Automating Data Subject Rights under DPDP Act 2023, GDPR, and RBI IT Security Guidelines*

## 📌 Project Overview
This repository provides an open-source framework for automating **Data Subject Access & Erasure Requests (DSAR/DSR)**. It bridges regulatory requirements with automated software execution pipelines.

### 🔑 Key Compliance & Engineering Features
- **Statutory Deadline Management:** Automatically tracks the 30-day fulfillment window (GDPR Art 12 / DPDP Act Sec 11).
- **Legal Hold Gatekeeping:** Prevents automated deletion if user data is subject to pending court litigation, regulatory investigations, or statutory tax retention rules.
- **Multi-System Discovery:** Maps endpoints across production databases, CRM applications, and cloud storage systems using Sensitive Data Intelligence (SDI) principles.
- **Audit Logging:** Generates immutable execution trails for regulatory compliance reviews.

## 📁 Repository Structure
- `dsr_workflow.yaml` — Declarative YAML pipeline defining identity verification, legal checks, and deletion stages.
- `dsr_engine.py` — Python simulation engine executing DSR processing logic.

## 👤 Author
**Abhishek Kishan**  
*Advocate | PrivacyOps & Corporate Compliance Specialist*  
[LinkedIn Profile](https://linkedin.com/in/abhishek-kishan)
python dsr_engine.py