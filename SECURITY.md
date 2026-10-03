# Security Policy

## Scope

This repository is a portfolio-grade PrivacyOps prototype. The supported application is intended for local demonstration with synthetic/demo data.

Do not use the application with production personal data, production credentials, or live enterprise systems unless the missing authentication, authorization, secret management, data protection, resilience, logging, monitoring and legal controls have first been implemented and reviewed.

## Reporting a vulnerability

Please do not publish sensitive vulnerability details in a public issue.

For a security concern, contact the repository maintainer privately through the contact details associated with the GitHub account. Include:

- affected file or endpoint
- steps to reproduce
- security impact
- any suggested remediation

Do not include passwords, API keys, access tokens, private keys, personal data or other secrets in the report.

## Secret handling

Never commit credentials or real personal data. Use environment variables or a managed secret store for future integrations.

The repository ignores common local secret and database artifacts, including environment files and SQLite database files.

## Intellectual property notice

**© 2026 Adv. Abhishek Kishan — All Rights Reserved.**

This repository and its original project materials are authored by Adv. Abhishek Kishan. This includes, but is not limited to, the original user interface, workflow design, architecture, documentation, configuration, source-code implementation and repository presentation. Public visibility of the repository does not constitute a licence to reuse, reproduce, redistribute, modify, rebrand or commercially exploit those materials.

Third-party dependencies remain subject to their own applicable licences. This notice does not claim exclusive copyright over abstract ideas, methods or concepts where applicable law does not protect them.
