# Security Policy

## Supported Versions

Only the latest released version of each package receives security updates.

## Reporting a Vulnerability

Please **do not** open a public issue. Instead, email [daniel.stancl@gmail.com](mailto:daniel.stancl@gmail.com) with a description, reproduction steps, and affected package(s). You can expect a response within 72 hours.

## What's in Place

- **CodeQL** and **Snyk** scan every push and PR for vulnerabilities
- **Rate limiting** on the agent API via `slowapi`
- **Read-only mode** (`ROSSUM_MCP_MODE=read-only`) to disable all write operations
- **Input sanitization** against path traversal and XXE attacks
- **CORS** restricted to allowed origins

## Credentials

Never commit tokens or secrets. Use environment variables or a `.env` file (gitignored).

```bash
export ROSSUM_API_TOKEN="your-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"
```
