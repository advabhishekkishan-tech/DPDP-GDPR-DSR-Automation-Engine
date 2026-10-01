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