# Phase 2: Durable persistence migration

## Objective

Move web-app metadata persistence from a container-local SQLite file to a configurable database backend, using PostgreSQL for hosted deployments and retaining SQLite for local development.

## Completed implementation and CI checkpoint

The Phase 2 branch now includes:
- a database connection layer that selects SQLite locally or PostgreSQL when `DATABASE_URL` is configured;
- versioned startup migrations recorded in `schema_migrations`;
- application tests that run the FastAPI startup lifecycle;
- tests for migration repeatability, anonymous-user ownership isolation, and case persistence across a new application lifespan;
- CI jobs for both SQLite and a PostgreSQL service container.

The latest CI run passed both application test jobs. The latest Security Checks workflow also passed CodeQL and dependency audit. This verifies the tested code paths in CI, but it does **not** yet prove that the hosted Render service is using durable PostgreSQL or survives a real deployment restart.

## Remaining risks and work

- Case and consent state, processor outcomes, and audit-event JSON are stored together in records; migration must preserve the API contract and audit verification behavior.
- A real Render/PostgreSQL cutover has not happened. Existing SQLite records are not copied automatically.
- Additional production-readiness work remains: exercise consent persistence across restart, review concurrent duplicate-request handling, and verify the deployed database configuration and persistence.
- PostgreSQL CI uses a temporary service container; it is not the eventual managed production database.

## Implementation sequence

1. **Completed:** introduce an explicit database connection layer and separate connection setup from schema changes.
2. **Completed:** add a PostgreSQL backend with parameterized queries and dictionary-like row access while retaining SQLite for local development.
3. **Completed:** run versioned migrations at application startup and record completed versions in `schema_migrations`.
4. **CI-tested:** run the application test suite against both SQLite and PostgreSQL, including owner isolation and case persistence across a new app lifespan.
5. **Next:** add/verify consent persistence and review concurrency and ownership edge cases.
6. **Pending:** decide whether any existing SQLite records need to be retained; if so, back them up and migrate deliberately.
7. **Pending:** configure managed PostgreSQL in Render, deploy only after review, and verify persistence across an actual service restart/redeploy.

## Safety constraints

- Never commit database credentials, session secrets, OAuth secrets, or production records.
- Do not automatically delete or overwrite the existing SQLite database.
- Keep mock enterprise connectors and synthetic-data warnings.
- Do not claim hosted persistence is complete until the configured Render service is verified against PostgreSQL and survives an actual restart/redeploy.
- Preserve owner checks in every case and consent query.
- Do not enter real data-subject information into this portfolio prototype.

## Acceptance criteria

- The app selects its database backend explicitly from configuration.
- On Render, missing `DATABASE_URL` fails clearly rather than silently falling back to ephemeral SQLite.
- Schema migrations are repeatable and versioned.
- SQLite and PostgreSQL CI suites pass.
- Tests demonstrate owner isolation and persistence across a new application lifespan.
- The hosted deployment is explicitly configured to use PostgreSQL and retains records after a real restart/redeploy.
- Any required SQLite-to-PostgreSQL data migration is planned and verified rather than assumed.
- Documentation states the prototype boundaries and the status of hosted persistence.
