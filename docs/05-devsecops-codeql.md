# 05 — DevSecOps and CodeQL without magic

**27 October 2026 — Advanced Cloud Architecture & DevOps CI/CD Pipeline Process**

DevSecOps adds security feedback to normal development and release work. One
scanner does not prove source code, dependencies, infrastructure, containers or
a live Azure deployment are secure. Repository scans run independently of the
teaching date; this is an October 27 workshop topic, not a prerequisite for the
October 17 Python/Docker foundations.

## CodeQL configuration

`.github/workflows/codeql.yml` runs on pushes and pull requests to `main`,
manual dispatch and a weekly schedule. Its matrix analyzes three language
categories: `python` (Flask backend), `javascript-typescript` (React frontend)
and `actions` (workflow files). It uses CodeQL action v4 with `build-mode:
none` and the checked-in `.github/codeql/codeql-config.yml` using
`security-extended` queries. Configured paths include `support-agent`,
`scripts` and `.github/workflows`; generated/dependency directories and tests
are excluded.

CodeQL builds a semantic representation of source and runs queries to detect
supported risky patterns and data flows. Successful analysis means the job
completed and findings were uploaded; it does not mean there are no alerts.
Review actual alerts and source flow, severity and remediation rather than
adding a deliberately unsafe sample just to populate a screenshot. CodeQL does
not scan runtime posture or replace dependency, image, IaC or secret scanning.

Permissions are scoped to the CodeQL job: read source and publish security
results, with workflow metadata access as configured. Scans need no Azure
credentials or OIDC token. Do not use privileged pull-request execution to work
around GitHub policy. Branch protection can require a scan job to run, but a
successful job is not itself an alerts threshold or a deployment gate.

## Workshop sequence

1. Map tests, CodeQL, image build, release approval and deployment. Identify
   which jobs block later work and which run independently.
2. Read the workflow and CodeQL config; review triggers, matrix, pinned actions,
   included paths and least-privilege permissions.
3. Inspect each language result and any alerts. For an alert, trace the finding
   and disposition; a zero-alert result only describes this scan's scope.
4. Distinguish requiring a workflow check from requiring no alerts. Configure
   merge protection explicitly if the repository plan and policy support it.
5. Check how release approvers inspect scan results. The current release
   workflow does not query CodeQL alerts or wait for an alerts policy.
6. Propose missing controls—dependency and secret scanning, container image
   vulnerability scanning, Terraform policy checks, SBOM/provenance and live
   configuration monitoring—as future work, not existing features.

## Application and infrastructure controls in this solution

- Flask applies `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  `X-Frame-Options: DENY`, and a Content Security Policy; API responses use
  `Cache-Control: no-store`. Request bodies are limited to 16 KiB.
- Specialist routes require a shared bearer token of at least 32 characters;
  the API fails closed when it is missing or a placeholder. Use HTTPS for
  deployed traffic and keep the secret in the pipeline environment/secret store.
- Customer ticket access keys are generated randomly. Only SHA-256 hashes are
  stored, comparisons use constant-time `secrets.compare_digest`, and the
  customer view does not expose internal ticket fields.
- Azure Blob Storage has shared keys and anonymous blob access disabled. App
  identity receives only Blob Data Contributor on `tickets` and Blob Data
  Reader on `knowledge`; deployment identity's knowledge upload role is scoped
  to that container.
- GitHub deploy uses OIDC; Azure Pipelines uses workload identity federation.
  App Service uses managed identity for ACR pull and Blob access.
- Pipeline release uses immutable backend and frontend ACR image digests.
  Both Docker targets run non-root (Python UID 10001, frontend Node user).
- Infrastructure OIDC uses GitHub environment dev. Bootstrap state storage is
  outside workload Terraform ownership; runtime identities cannot access state.
  Configure required reviewers explicitly: federation alone is not approval.

These are useful safeguards, not a complete security certification. Review
source, roles, runtime configuration and the exact release artifact together.

## Known limitations and extension ideas

| Current limitation | Possible next step |
| --- | --- |
| No rate limiting on public ticket creation; requests can trigger paid model calls. | Add gateway/app-level throttling, abuse monitoring and quotas. |
| One shared specialist token; no per-user specialist identity or audit attribution. | Integrate Entra ID, for example App Service Easy Auth, and per-user authorization. |
| `LocalStore` is single-process and unsuitable for scaled production instances. | Use the configured Azure Blob store (used in Azure). |
| No email delivery; customers see status/replies in the portal. | Add Azure Communication Services with consent, delivery and privacy controls. |
| Storage public network access remains enabled; there is no private endpoint. | Add private networking and validate DNS, routing and access policy. |

The storage account still uses Entra-only authorization; public network access is
a network exposure setting, not a shared-key setting. CodeQL does not scan Azure
resource posture, and the delivery pipeline does not enforce an alerts threshold.

## Release review

Before approval, verify the reviewed commit, backend/frontend tests, CodeQL
results and open alerts, identity scope, token handling and digest. Afterward,
verify the live health/configuration/knowledge checks and logs. A source scan
cannot establish that a support draft is accurate; the human approval step
remains part of the safety design.

References: [CodeQL supported languages](https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/),
[CodeQL action](https://github.com/github/codeql-action),
[GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions).
