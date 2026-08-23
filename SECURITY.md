# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report vulnerabilities privately through GitHub's
[Report a vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
flow on this repository, under **Security → Advisories**.

Please include reproduction steps, the affected version or commit, and the
impact you believe it has. You can expect an initial response within a week.

## Scope

Atlas is a **local-first, single-user desktop application**. It binds to
`127.0.0.1` and ships with **no authentication**, because it assumes the only
user is the person sitting at the machine.

**Do not expose Atlas to a network or the public internet.** Doing so gives
anyone who can reach the port full access to your documents and the ability to
spend your API credits. Multi-user deployment is out of scope, and issues that
depend on deliberately exposing the app to untrusted networks will be treated
as configuration errors rather than vulnerabilities.

In scope:

* API key disclosure — in logs, error messages, HTTP responses, or request URLs
* Path traversal or arbitrary file read/write via uploads or any endpoint
* Weaknesses in the encrypted keystore or its key-file permissions
* Ways for uploaded document content to execute code or escalate privileges
* Dependency vulnerabilities with a practical exploit path in Atlas

## How keys are handled

API keys are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) and written to
`~/.atlas/config/secrets.enc`. The encryption key lives in a separate file whose
permissions are restricted to the current user.

Keys are additionally protected at runtime:

* sent as request **headers**, never in URLs or query strings
* passed through a redaction layer applied to all log output, including
  tracebacks, so they cannot reach `~/.atlas/logs/`
* never returned by the API — the settings endpoints report only whether a
  provider is configured

If you believe a key of yours has been exposed, rotate it with the provider
immediately, then remove it in **Settings** and add the new one.
