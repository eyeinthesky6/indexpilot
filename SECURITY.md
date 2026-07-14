# Security Policy

## Supported Version

Security fixes are made on the current `main` branch while IndexPilot is in open-source preview.
There is no supported production release line yet.

## Reporting a Vulnerability

Use the repository's private **Report a vulnerability** option when it is available. If it is not
available, contact the repository owner through GitHub before sharing technical details. Do not put
secrets, credentials, customer data, or a working exploit in a public issue.

Include the affected commit, reproduction steps, impact, and any suggested mitigation. Maintainers
should acknowledge a private report before publishing details.

## Deployment Boundary

The dashboard API requires `INDEXPILOT_API_TOKEN` by default. Only the `/` liveness route is public;
API, OpenAPI, and documentation routes use the same centralized bearer-token check. Non-loopback
startup through `indexpilot-api` is refused when auth is disabled or unconfigured.

This is a single-operator control, not multi-user authentication or RBAC. Keep the service private,
use HTTPS or a trusted reverse proxy, rotate exposed tokens, and leave index creation in advisory
mode unless an operator has reviewed and explicitly approved apply mode.
