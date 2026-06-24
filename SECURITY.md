# Security Policy

## Supported versions

Security fixes are applied to the latest release on [PyPI](https://pypi.org/project/meris-agent/) and the `main` branch of this repository.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, email the maintainers with:

- A description of the issue and potential impact
- Steps to reproduce (proof-of-concept if available)
- Affected version(s) and environment (OS, Python version)
- Your suggested fix, if any

We will acknowledge receipt and work on a fix. We ask that you allow reasonable time before public disclosure.

## Scope notes

- **Meris Agent** (this repo): CLI, Harness, local sandbox, VS Code extension.
- **Meris Cloud** (hosted SaaS): not in this repository — report Cloud-specific issues through the product's official channel when available.

## Safe defaults

- Do not commit API keys (`.env` is gitignored).
- Do not expose `meris ui` to the public internet without authentication — local UI sessions are not designed as a multi-tenant server.
- Review `.meris/settings.yaml` permissions before running `meris run` on untrusted prompts.
