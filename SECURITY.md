# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository. Do not open a public issue.

We aim to acknowledge reports within 72 hours.

## Scope notes

- paper-preflight sends only metadata of cited works (DOIs, titles, authors, years) to public
  scholarly APIs. Any path that would send manuscript text, file paths or credentials to a
  third party is a security bug.
- API keys and contact emails are read from environment variables only and must never be
  logged, printed, cached or written into reports.
- The MCP server must not read or write files outside the workspace root it was started with.
