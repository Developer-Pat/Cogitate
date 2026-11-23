# Security Policy

## Supported Versions

Currently, only the latest version of Cogitate is supported with security updates.

| Version | Supported          |
|---------|-------------------|
| 0.1.x   | ✅ Active         |

## Dependencies

Cogitate installs from two lockfiles: `uv.lock` at the repository root (one uv workspace, whose member is
`backend`) and `frontend/package-lock.json`. Dependabot watches both weekly and opens grouped minor/patch pull
requests. `scripts/diagnostics/audit_dependencies.py` is the independent second opinion — it asks OSV, the
advisory database Dependabot ingests, about the exact versions the lockfile resolves, and separates direct
dependencies from transitive ones.

A dependency update ships only behind the same gate as any other change: the four fast test groups, `tsc -b`, the
frontend test suite and the frontend build.

### Accepted risks

These findings are open on purpose. Each closes only with a major-version jump of a build or test tool, or of a
parent that has to take one. Three are build/test tooling with no path into a running install; the fourth is a
rendering helper whose advisory needs crafted input plus user interaction. None grants code execution, privilege
escalation or data access on its own, and there is no open critical or high finding.

| Package | Severity | Pinned by | What closes it |
|---|---|---|---|
| `@vitest/mocker` | moderate | `storybook` 9 pins 3.x | storybook 10 |
| `postcss-selector-parser` | moderate | `@tailwindcss/typography` | a typography release on 6.1.5 or later |
| `minimatch` | moderate | `glob` 10, via storybook's docgen plugin | the glob 14 chain |
| `katex` (shipped, via `mermaid`) | low | `mermaid` | a mermaid release on katex 0.18 |

The live list is the repository's [Security tab](https://github.com/Developer-Pat/Cogitate/security/dependabot);
this table records only the findings already decided.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in Cogitate, **please do not open a public Issue**.

Instead, report it privately:

1. **Use the repository's private reporting channel** — Security → Advisories → *Report a vulnerability* in the
   [Security tab](https://github.com/Developer-Pat/Cogitate/security/advisories/new). That opens a private advisory
   only you and the maintainers can see.
2. **Contacting the repository maintainer** directly through GitHub, if the advisory form is not available.

### What to Include

- A clear description of the vulnerability
- Steps to reproduce it (if possible)
- The potential impact
- Any suggested remediation (optional)

### Response Timeline

- **Acknowledgement:** Within 5 business days
- **Initial Assessment:** Within 10 business days
- **Fix or Mitigation:** Timeline depends on severity and complexity

We will keep you informed of progress throughout the process.

## Disclosure Policy

We follow a coordinated disclosure approach:

1. The reporter submits a vulnerability report privately.
2. We confirm receipt and begin assessment.
3. We work on a fix and prepare a release.
4. Once a fix is released, we publicly disclose the vulnerability with credit to the reporter (if desired).

We appreciate your help in keeping Cogitate and its users safe.