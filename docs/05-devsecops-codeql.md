# 05 — DevSecOps and CodeQL without magic

DevSecOps puts security feedback into the development/release process. It does not mean one scanner proves an application, image, infrastructure, or cloud subscription is secure.

## Use across both sessions

- **17 October 2026:** introduce source scanning, run the provided workflow and
  explain how to read its results.
- **27 October 2026 — Advanced Cloud Architecture & DevOps CI/CD Pipeline
  Process:** revisit the same workflow to distinguish successful analysis from
  an alerts policy, examine approval and identity boundaries, and discuss where
  additional security controls belong in the release process.

The advanced discussion does not silently enable those additional controls.
The implementation and limitations below remain the source of truth.

This repository includes a concrete [CodeQL workflow](../.github/workflows/codeql.yml), not only a slide example. It analyzes the Python API and the browser JavaScript in `launchpad-lab/static/app.js`.

## What CodeQL actually does

CodeQL builds a semantic database from **source code**, then runs queries looking for patterns such as unsafe data flow, injection, or other supported language-specific weaknesses. Analysis is deeper than searching for dangerous words, but it is still limited by extraction, query coverage, and the code paths modeled.

The matrix uses current supported language IDs:

```yaml
language: [python, javascript-typescript]
```

Each language runs a separate job with `build-mode: none`. Python and JavaScript do not require a compiler build for this extraction mode. The initialize step selects the language and the analyze step publishes findings with a separate language category. Tests/builds do not replace analysis and are not needed solely for CodeQL extraction here.

The original training example's `github/codeql-action/*@v2` is outdated. This repository pins **CodeQL action v4** to an immutable commit, alongside pinned checkout; do not paste the old v2 snippet into a new workflow. Keep pins updated through reviewed action upgrades. Both current supported language identifiers and action major versions matter.

## Triggers and permissions

The workflow runs on:

- pushes to `main`;
- pull requests targeting `main`;
- manual dispatch;
- Mondays at 06:23 UTC (scheduled scans use the default branch; execution can be delayed).

It does **not** sign in to Azure or deploy anything. `contents: read` permits checkout. `security-events: write` permits publishing code-scanning results; `actions: read` supports workflow metadata/access where needed. These permissions are scoped to the analysis jobs, not granted to every workflow in the repository. No `id-token`, cloud secrets, or broad repository-write token is needed for scans.

For this public repository, GitHub CodeQL/code scanning is available without the private-repository paid entitlement. Availability for private repositories depends on the applicable GitHub plan/security product. Fork PR token permissions and code-scanning upload behavior are governed by GitHub; do not switch to `pull_request_target` with untrusted checkout or add privileged secrets as a workaround.

## Enable it and find the result

1. Open **Settings → Code security** (or **Code security and analysis**, depending on UI).
2. Use **advanced setup** / the checked-in workflow. If default setup is already enabled, disable it before using the advanced workflow to avoid duplicate/conflicting scans.
3. Open **Actions → CodeQL**, run the workflow on `main`, and inspect both language jobs.
4. Open **Security → Code scanning** to inspect alerts. Review source locations, the data-flow path when provided, severity, and the suggested explanation.
5. Fix a real finding in a branch, add a regression test if appropriate, open a PR, and verify the alert is resolved in a new scan. Dismiss false positives only with a recorded reason.

No alerts means **no alerts from this scan**, not “no vulnerabilities.” This small demo is not intentionally seeded with unsafe code; a successful zero-alert result is expected to be possible. Do not add a public exploitable endpoint just to make a screenshot.

## Scan success is not an alerts gate

The provided workflow is **standalone scanning**, not a deployment security gate:

- A successful `Analyze (python)` or `Analyze (javascript-typescript)` job means analysis/upload succeeded. Those jobs can succeed **while alerts exist**.
- Branch protection/rulesets can require those checks and the CI Python/Terraform checks before merging. That ensures execution, not absence of findings.
- To block merges on findings, separately configure GitHub **code-scanning merge protection** where available, selecting tools and severity thresholds. Verify its behavior on a controlled test PR; do not assume requiring the workflow check implements it.
- The manual Azure release workflow has its own test gate and environment approval, but does not query alerts or await CodeQL. Approvers should review the commit's CI, scanning status, and outstanding alerts. Requiring a separate alerts gate before **deployment** needs an explicit additional integration/policy.
- Azure DevOps does not run this GitHub CodeQL workflow as part of its stages. GitHub scans the connected repository; that is not an automatic Azure DevOps release gate.

## What this demo covers — and does not

| Layer | Present here | What it does not prove |
| --- | --- | --- |
| Application behavior | Python HTTP tests | all business edge cases/security properties |
| Source semantics | CodeQL Python + JavaScript | container-package CVEs, complete Terraform policy compliance, live cloud posture |
| Infrastructure syntax/schema | Terraform format/validate | safe networking, least privilege, cost limits, drift |
| Cloud authentication | GitHub OIDC / Azure DevOps WIF, target managed identities | that every authorized workflow change is safe |
| Release integrity | same ACR SHA-256 digest on both targets | signed provenance or an SBOM |
| Release control | manual main-only release + external environment approvals | automatically blocking outstanding alerts |

CodeQL is **not a universal misconfiguration scanner**. It does not replace Terraform policy checks, Docker image vulnerability scans, dependency auditing, secret scanning, or live configuration review. No image-CVE gate is included in these beginner pipelines; the image is built and pushed after tests. Add those tools as a deliberate next exercise rather than claiming CodeQL already provides them.

Similarly, **Microsoft Defender for Cloud is not automatically integrated** by enabling CodeQL, using Azure login, or deploying into Azure. Defender plans, DevOps connectors, permissions, and any release-policy wiring require separate configuration and may have costs. No Defender connector or subscription policy is created by this repository.

## Review habit for beginners

Before approving a release:

1. Confirm you are deploying a reviewed `main` commit and a recorded immutable image.
2. Read the CI results and both language scan results; inspect alerts, not only green workflow badges.
3. Check the federated identity, resource-group/registry scopes, and target managed identities.
4. Remember Run Command is root execution and public VM HTTP is demo-only.
5. Keep a known-good digest for deliberate rollback and read readiness/log output after release.

Action versions verified through GitHub's public API when this example was authored: checkout **v7.0.1**, setup-python **v7.0.0**, Azure login **v3.1.0**, setup-terraform **v4.0.1**, and CodeQL action **v4.38.3**. The files pin full commit SHAs rather than moving tags; annotated tags were resolved to their underlying commits. Update them as a reviewed maintenance task.

### References

- [CodeQL supported languages/frameworks](https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/)
- [CodeQL action](https://github.com/github/codeql-action)
- [Advanced code-scanning setup](https://docs.github.com/en/code-security/code-scanning/creating-an-advanced-setup-for-code-scanning)
- [CodeQL build modes](https://docs.github.com/en/code-security/code-scanning/creating-an-advanced-setup-for-code-scanning/codeql-code-scanning-for-compiled-languages)
- [Code-scanning merge protection](https://docs.github.com/en/code-security/code-scanning/managing-your-code-scanning-configuration/configuring-code-scanning-merge-protection)
- [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
- [Defender for Cloud DevOps security overview](https://learn.microsoft.com/azure/defender-for-cloud/defender-for-devops-introduction)
