# Security Policy

## Supported Version

Security fixes are made on the current `main` branch while IndexPilot is in open-source preview.
There is no supported production release line yet.

## Reporting a Vulnerability

Use the repository's private **Report a vulnerability** option. Private vulnerability reporting is
enabled for IndexPilot. Do not put secrets, credentials, customer data, or a working exploit in a
public issue.

Include the affected commit, reproduction steps, impact, and any suggested mitigation. Maintainers
should acknowledge a private report before publishing details.

## Deployment Boundary

The public `indexpilot review` command starts a read-only transaction. Proposed `CREATE INDEX` text
is parsed locally and rebuilt from validated identifiers; the supplied string is never executed.
Reports retain fingerprints rather than raw workload SQL. They still expose schema, table, column,
index, database, and workload-volume metadata, so review artifacts before sharing them.

The dashboard API started through `indexpilot-api` defaults to passwordless access only when bound
to a loopback host such as `127.0.0.1`. To require a token explicitly, set
`INDEXPILOT_API_AUTH_MODE=required` and `INDEXPILOT_API_TOKEN`; API, OpenAPI, and documentation routes
then use the same centralized bearer-token check. The static UI, minimal `/` liveness response, and
`/api/access` mode check remain public so the login screen can load; they contain no database
results. Non-loopback startup is refused when auth is disabled or unconfigured.

This is a single-operator control, not multi-user authentication or RBAC. Keep the service private,
use HTTPS or a trusted reverse proxy, rotate exposed tokens, and leave index creation in advisory
mode unless an operator has reviewed and explicitly approved apply mode.
