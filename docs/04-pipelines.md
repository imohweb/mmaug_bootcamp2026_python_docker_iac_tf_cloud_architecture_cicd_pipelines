# 04 - Infrastructure and application CI/CD

Use [skills.md](../skills.md) as the reusable operational runbook and the
[README](../README.md) for local/cloud startup and architecture.

## Infrastructure: GitHub Actions

[infra.yml](../.github/workflows/infra.yml) bootstraps storage before Terraform
initialization, then plans/applies infrastructure in existing
`RG-MMAUG-Bootcamp`. It uses the existing SP `mmaug_bootcamp_spn_2026` with OIDC
and GitHub environment **dev**, matching the existing federation.

The pipeline must consume the saved plan it presents for review. Do not apply
untrusted pull-request code with Azure credentials. State, plans and outputs
are sensitive; keep artifact retention short and never print raw plan JSON.
Bootstrap and apply are paid operations and require explicit authorization.

Bootstrap storage has private `tfstate`, `knowledge` and `tickets` containers.
It is not owned by the Terraform app root module, so destroying the workload
cannot destroy its own backend. An earlier local deployment requires state
migration before the first remote-state run.

Contributor on the RG is not enough for Terraform RBAC or Blob data operations.
An administrator must prepare scoped RBAC administration and data roles before
dispatch. Scripts do not auto-escalate. Required reviewers and branch
restrictions must be configured externally on dev; OIDC alone is not approval.
See the actual workflow for current input and variable names.

## Application: GitHub Actions

[ci.yml](../.github/workflows/ci.yml) tests Python, React and the Node API proxy,
builds images and smoke-tests the split topology, validates Terraform and runs
offline deployment tests. Pushes and PRs do not deploy. After reviewing successful
CI for the commit and obtaining release authorization, manually dispatch
[deploy.yml](../.github/workflows/deploy.yml) on `main`.

The release uses dev OIDC, builds Docker targets backend and frontend, pushes
`support-agent-backend` and `support-agent-frontend` with unique tags, resolves
both digests and deploys them through the shared script.

Environment variables:

```text
AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP=RG-MMAUG-Bootcamp
ACR_NAME, BACKEND_WEB_APP_NAME, FRONTEND_WEB_APP_NAME
```

Environment secret: **SPECIALIST_API_TOKEN**, random and at least 32 characters.
Configure infrastructure-specific storage/prefix values as named in infra.yml.
No client secret, account key or publish profile is needed.
Azure login's `SERVICE_PRINCIPAL` auth type also covers OIDC federation; it does
not imply a client secret. The release validates configuration before login and
reports missing `dev` variables explicitly.

## Azure Pipelines: application-only alternative

[azure-pipelines.yml](../pipelines/azure-pipelines.yml) retains Test -> Build ->
Deploy for the two images. Variable group mmaug_bootcamp_var holds subscription,
resource group, ACR and both web app names, with SPECIALIST_API_TOKEN marked
secret and explicitly mapped. The azure-demo-wif service connection and
azure-demo Azure DevOps environment require independent configuration; GitHub
OIDC does not authorize Azure DevOps.

Queue deploy=false for tests only. Its default is true, and successful
non-PR main runs can release. It does not run the GitHub infrastructure
workflow. Select one orchestrator per target.

## Deployment and recovery

[deploy-azure.sh](../scripts/deploy-azure.sh) receives BACKEND_IMAGE_REF and
FRONTEND_IMAGE_REF as ACR digests, plus the two app names and secret token.
It configures the backend first, verifies health/config/knowledge, then
configures the frontend and verifies the proxied API and React shell.
The frontend BACKEND_ORIGIN points to the HTTPS backend origin.

The operation is not atomic. On failure, inspect both app images/logs before
an authorized rollback with a known-good pair of digests. Do not guess mutable
tags. Finish release verification with a synthetic submit/review/approve/track
workflow and a real indexed-retrieval check; template fallback is not evidence
of a working index.

CodeQL runs separately for Python, JavaScript/TypeScript and Actions. A green
scan is not an automatic alerts-based deployment gate. Configure branch
protections and review policies deliberately.

[workflows/codeql.yml](../.github/workflows/codeql.yml) is the executable workflow.
[codeql/codeql-config.yml](../.github/codeql/codeql-config.yml) is its referenced
query/path configuration, not a second pipeline. Keep both files.
