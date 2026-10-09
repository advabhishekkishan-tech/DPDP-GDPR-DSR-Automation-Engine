# Phase 2: Durable persistence migration

## Objective

Move web-app metadata persistence from a container-local SQLite file to a configurable database backend, using PostgreSQL for hosted deployments and retaining SQLite for local development where practical.

## Current risks

- `app.py` opens `privacyops.db` relative to the application directory. This is not durable storage on an ephemeral hosted filesystem.
- Schema creation and `owner_id` column upgrades happen inside request-time database initialization.
- Application SQL uses SQLite-specific connection and row behavior in several places.
- Case and consent state, processor outcomes, and audit-event JSON are persisted together in single records, so migration must preserve the current API contract and audit verification behavior.

## Implementation sequence

1. Introduce an explicit database configuration layer and separate connection/schema initialization from request handling.
2. Add a PostgreSQL backend with parameterized queries and dictionary-like row access; keep SQLite as the local/test backend.
3. Move schema evolution into versioned migrations. Do not rely on ad-hoc request-time `CREATE TABLE` / `ALTER TABLE` calls in hosted production.
4. Add integration tests against both SQLite and PostgreSQL for:
   - case creation, listing, retrieval, and owner isolation;
   - consent creation, withdrawal, repeated withdrawal, and evidence retrieval;
   - anonymous-to-Google-user record ownership migration;
   - activity events and admin-only analytics;
   - duplicate DSR detection and concurrent inserts.
5. Document deployment configuration and a safe migration/cutover procedure.
6. Configure a managed PostgreSQL database in the hosting environment, deploy to a preview/staging target if available, and verify persistence across restart/redeploy before treating it as durable.

## Safety constraints

- Never commit database credentials, session secrets, OAuth secrets, or production records.
- Do not automatically delete or overwrite the existing SQLite database.
- Keep mock enterprise connectors and synthetic-data warnings.
- Do not claim the migration is complete until PostgreSQL integration tests pass and persistence has been verified on the deployed service.
- Preserve session ownership constraints in every case and consent query.

## Acceptance criteria

- The app selects its database backend explicitly from configuration.
- PostgreSQL is used for hosted deployment when configured; missing/invalid configuration fails clearly rather than silently falling back to ephemeral SQLite.
- Schema migrations are repeatable and versioned.
- Existing API behavior and the current test suite remain green.
- Tests demonstrate owner isolation and persistence after application restart.
- README documents local setup, hosted environment variables, migration limitations, and the prototype boundary.
