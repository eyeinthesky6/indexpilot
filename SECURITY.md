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

The dashboard API requires `INDEXPILOT_API_TOKEN` by default. Only the `/` liveness route is public;
API, OpenAPI, and documentation routes use the same centralized bearer-token check. Non-loopback
startup through `indexpilot-api` is refused when auth is disabled or unconfigured.

This is a single-operator control, not multi-user authentication or RBAC. Keep the service private,
use HTTPS or a trusted reverse proxy, rotate exposed tokens, and leave index creation in advisory
mode unless an operator has reviewed and explicitly approved apply mode.
