# Reusable instructions: MMAUG support agent

Audience: workshop participants, maintainers and coding assistants.
Use when running locally, changing the application, preparing infrastructure
or releasing the two web apps. Commands start at the repository root.

This is a shared runbook, not an automatically installed agent skill. Assistants
should read it explicitly. A discoverable skill would additionally require
the appropriate `SKILL.md` packaging; do not assume this file is auto-loaded.

## 1. Invariants and authorization boundaries

- Target only the existing **RG-MMAUG-Bootcamp**, not a newly created group.
- Cloud hosting: two App Service web apps (frontend and backend); no VM.
- State bootstrap owns the storage account with isolated `tfstate`, `knowledge`
  and `tickets` containers. Three containers were chosen to keep ticket data
  separate from state and indexed source documents.
- Terraform must not own/delete the RG or the account holding its own backend.
- GitHub identity: existing `mmaug_bootcamp_spn_2026`, OIDC environment `dev`.
  Reuse the existing trust; do not create a client secret.
- Preserve unrelated work. Do not commit, push, trigger paid workflows, change
  role assignments, apply or destroy without explicit authorization.
- Never print tokens, state, plan JSON, customer queries or access keys in CI/chat.
- Keep synthetic data in tests. Do not expose local dev servers publicly.
- Only one orchestrator may release to a shared target at a time.

## 2. Responsibilities and source of truth

| Surface | Owner |
| --- | --- |
| Existing RG | Administrator, read-only Terraform data source |
| Storage account and private containers | Idempotent infrastructure bootstrap |
| Remote state | Terraform Azure backend with Entra/OIDC and blob lease locking |
| App plan, two apps, ACR, Foundry and Search | Azure Terraform root module |
| Existing web identity and all role assignments | Administrator; Terraform reads/attaches the identity but grants no roles |
| Knowledge ingestion / agent configuration | Infrastructure setup and index checks |
| Container image digests and specialist token setting | Application release pipeline |
| Ticket approval | Human specialist, never an unattended model action |

Use [README](README.md) and [architecture](docs/architecture.md) to trace the
components. Do not conflate the Terraform state container, source documents,
Search index and ticket JSON: they have different identities and permissions.

## 3. Local development workflow

Prerequisites: Python 3.10+, Node.js 22+, npm, curl; Docker for containers;
Terraform 1.5 to below 2.0, Azure CLI and jq for infrastructure work.

```bash
# First setup, only if the environment/dependencies are absent:
python3 -m venv support-agent/backend/.venv
support-agent/backend/.venv/bin/pip install -r support-agent/backend/requirements.txt
(cd support-agent/frontend && npm ci && npm run build)

# Terminal 1: offline backend, also serves built React for the simple local lab
cd support-agent/backend
export AI_MODE=off STORAGE_ACCOUNT_URL='' AZURE_STORAGE_CONNECTION_STRING=''
export SPECIALIST_API_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
.venv/bin/python app.py
```

The empty storage variables override `.env-local` cloud settings. Use the
working backend virtual environment, not the deleted old `support-agent/.venv`.
Local data persists in `.data`; do not delete it without approval.

Optional terminal 2, starting at repo root:

```bash
cd support-agent/frontend
npm run dev -- --host 127.0.0.1
```

Simple local portal: port 8000. Vite hot reload: normally 5173 with API proxy
to 8000. Specialist route: `/#/specialist`. Copy the token privately, not into
chat or logs. Ctrl+C stops foreground servers. For temporary automated checks,
record the exact process/session, verify readiness and stop it in cleanup.

## 4. Rehearse the two-container topology

```bash
export SPECIALIST_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose -f support-agent/compose.split.yaml up --build -d
curl -fsS http://127.0.0.1:8090/health
curl -fsS http://127.0.0.1:8090/api/config
docker compose -f support-agent/compose.split.yaml logs --tail=50
docker compose -f support-agent/compose.split.yaml down
```

The frontend serves React and proxies API/health to the backend. Production
`BACKEND_ORIGIN` is the HTTPS backend web app origin; local Compose uses
`http://backend:8000`. No CORS workaround or browser-held cloud credential is
needed. The default Docker target and original Compose retain the one-container
foundations lab; cloud builds explicitly select `--target backend` or
`--target frontend`.

## 5. Verification requirements

```bash
(cd support-agent/backend && .venv/bin/python -m unittest -v)
(cd support-agent/frontend && npm test && npm run build && node --test server.test.mjs)
bash -n scripts/deploy-azure.sh scripts/bootstrap-state.sh
bash tests/test-deploy.sh
bash tests/test-bootstrap-state.sh
for directory in support-agent/terraform infra/azure; do
  (cd "$directory" && terraform fmt -check -recursive &&
    terraform init -backend=false -input=false && terraform validate)
done
git diff --check
```

Do not reinstall packages unless setup is needed or manifests changed.
Validate only the relevant surfaces for a focused change.

For end-to-end behavior, submit a synthetic duplicate-charge query, confirm
billing / Aye Chan, verify the customer cannot see the draft, inspect knowledge
sources, edit/approve and verify the exact customer response. Test reassignment
with another ticket. Passing `/health` alone is not proof of persistence,
index retrieval or approval correctness.

## 6. GitHub access and identity

```bash
gh auth switch --hostname github.com --user imohweb
gh api user --jq .login
gh workflow list
```

GitHub CLI, Azure CLI and the VS Code Azure extension can have different
accounts/tenants. Read the current Azure CLI subscription before cloud work;
do not silently switch tenants to make a failing command pass.

The federated credential's issuer is GitHub Actions and its audience is
`api://AzureADTokenExchange`. The existing subject targets `dev` and contains
immutable repository/owner IDs. Match it to the repository's token format;
do not replace it with a guessed name-only subject.

Configure **GitHub environment `dev`**:

- Azure login variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
  `AZURE_SUBSCRIPTION_ID`.
- Infrastructure target: `AZURE_RESOURCE_GROUP=RG-MMAUG-Bootcamp`,
  `STATE_ACCOUNT` (globally unique storage name), `RESOURCE_PREFIX` and optional
  `FOUNDRY_LOCATION` (defaults to eastus2), as named in
  [infra.yml](.github/workflows/infra.yml).
- Runtime identity: `WEB_IDENTITY_RESOURCE_ID`, the full resource ID of the
  existing user-assigned identity for both web apps. This is separate from the
  deployment SP's `AZURE_CLIENT_ID`; backend SDK configuration uses the
  runtime identity client ID resolved by Terraform.
- Application variables: `ACR_NAME`, `BACKEND_WEB_APP_NAME`,
  `FRONTEND_WEB_APP_NAME` from infrastructure outputs.
- Application secret: `SPECIALIST_API_TOKEN`, generated randomly, at least
  32 characters, not a placeholder.
- Required reviewers and branch restrictions. At inspection time `dev` had
  no protections or configuration values; YAML does not create those controls.

## 7. Administrator prerequisites

The existing SP has Contributor at RG scope. That is deliberately not sufficient
for every action:

1. Resource Contributor allows resources within this RG, not subscription-wide
   provider registration or creation of another group.
2. Terraform does not create role assignments. Administrators own existing
   runtime/service grants and the deployment SP's permission to read/attach
   the web identity. Verify the [permission matrix](README.md#required-azure-permissions)
   before setting the workflow input `external_access_verified=true`; apply
   fails closed without that attestation. Plan-only runs remain available.
   Search/project system identities require separately administered provisioning
   and access, with reviewed imports when needed, before a complete apply.
   No role-management permission is required for Terraform itself.
3. Bootstrap/state operations need Storage Blob Data Contributor. A newly
   created account requires either an approved inherited data role or a
   separate administrator bootstrap, followed by account-scoped access.
4. Search and Foundry configuration need the corresponding data-plane roles.

An authorized administrator must prepare these roles. The pipeline must fail
clearly when access is missing, not grant itself Owner or silently use keys.
Register needed resource providers separately when the identity cannot.
Never print OIDC tokens or use an interactive personal login in CI.

## 8. Infrastructure pipeline procedure

Read [infra.yml](.github/workflows/infra.yml), its input names and bootstrap
script before dispatch. Infrastructure execution is manual and privileged:

Dispatch inputs: `state_ready` must explicitly confirm reviewed/migrated state.
`apply` defaults to false; even a plan-only run can create paid bootstrap storage.
Apply runs as a separate job using the same saved plan and refuses to proceed
without configured required reviewers on `dev`. The workflow reads environment
protection metadata through GitHub's API; inability to read it fails closed.

1. Verify the source branch/commit, environment, subscription and existing RG.
2. If earlier Terraform state exists, review and migrate it first. Never allow
   a fresh remote state to duplicate resources already managed locally.
   If it tracks role assignments, arrange reviewed removal of their state
   ownership without deleting the actual grants before using this configuration.
   Never approve a plan that deletes those existing permissions.
3. Run bootstrap before `terraform init`: create/reuse Entra-only StorageV2 and
   the three containers, without managing that storage in the app root module.
4. Initialize the Azure backend with OIDC and the private state container.
5. Validate and create the plan. Protect saved plans as sensitive artifacts.
6. Review the exact plan and its commit. Apply that plan only after the intended
   approval boundary; do not re-plan silently after approval.
   For a completed plan-only run, use the manual
   [reviewed-plan apply workflow](.github/workflows/apply-reviewed-plan.yml)
   with the reviewed run ID, attempt, full SHA and artifact ID. It verifies
   source provenance, artifact expiry/digest/contents and environment
   protection before applying the exact artifact at its source SHA. It never
   bootstraps or re-plans. External-access attestation and the environment
   reviewer remain mandatory; failed verification or stale state must stop.
7. Verify knowledge indexing and agent retrieval setup. An accepted indexer
   start request is not equivalent to successful ingestion.
8. Record outputs for application release variables. Do not print secrets or
   automatically trigger deployment before infrastructure is ready.

Azure Pipelines currently provides application delivery only. GitHub federation
does not create Azure DevOps WIF trust; configure its service connection
separately if using that alternative.

## 9. Application release procedure

GitHub pushes and pull requests run CI only, not deployment. Manually dispatch
[deploy.yml](.github/workflows/deploy.yml) on `main` only with release authorization
and reviewed successful CI evidence for that commit. Configure the `dev`
variables and secret first; OIDC needs client, tenant and subscription IDs but
no client secret. `SERVICE_PRINCIPAL` in Azure login logs does not mean
secret-based authentication.

The release builds two images with the same source commit, pushes unique tags,
resolves immutable digests and calls [deploy-azure.sh](scripts/deploy-azure.sh).
Its contract:

```text
AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, ACR_NAME
BACKEND_WEB_APP_NAME, FRONTEND_WEB_APP_NAME
BACKEND_IMAGE_REF=<acr>.azurecr.io/support-agent-backend@sha256:<64 hex>
FRONTEND_IMAGE_REF=<acr>.azurecr.io/support-agent-frontend@sha256:<64 hex>
SPECIALIST_API_TOKEN (secret)
```

It checks both API endpoints and the React shell, with explicit failure and
diagnostics. Tokens are passed through a private settings file/stdin rather than
command arguments. Linux runners need GNU `timeout`, Azure CLI, curl and jq.
The deployment is not atomic across two apps: on failure, inspect both image
digests and logs. Roll back only with an authorized known-good pair of digests.

## 10. Grounding, costs and maintenance

Knowledge source: [Markdown](support-agent/knowledge) -> Blob -> AI Search /
Foundry IQ retrieval -> drafting agent -> human approval. Source uploads,
indexing and retrieval must all be tested; template fallback is not evidence
that cloud grounding succeeded. `AI_MODE=off` remains the safe offline default.

App Service plan, ACR, Search, Storage and AI usage can incur costs. Never
destroy the existing RG, state or unrelated resources. Inspect a destroy plan
and retain state until managed resources are gone; bootstrap storage cleanup
requires a separate explicit decision.

Keep README, architecture, participant slides and this runbook synchronized
when pipeline variables or resource topology change. The [PDF builder](scripts/build-participant-pdf.py)
uses ReportLab as documentation tooling, not an application dependency:

```bash
python3 scripts/build-participant-pdf.py
```

Render and inspect the PDF before sharing. Keep the limitations explicit:
shared specialist token, no rate limiting, public endpoints and portal-only
delivery. Do not claim live cloud verification from offline mock tests.

## 11. Presentation-day GitHub Actions deployment (opt-in)

Use this procedure only when the presenter explicitly asks the agent to run
the GitHub deployment during the presentation. The target is GitHub repository
[`imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines`](https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines),
GitHub environment `dev`, and the environment settings page is
[here](https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines/settings/environments/24587402017/edit).
Today’s deployment path is GitHub Actions only. The Azure Repo is for learner
walkthrough; do not push to it, run Azure Pipelines, or use it to deploy.

Suggested presenter prompt:

> Read `skills.md` and follow Section 11 for the GitHub-only presentation
> deployment. Authenticate as `imohweb`, verify the repository and target
> branch, align the four GitHub workflow files, and populate only verified
> `dev` variables. Stop at every presenter pause: have me add the secret
> directly in GitHub, review and approve the Terraform plan/apply, and approve
> the app release. Run CI and CodeQL for the exact commit. Do not push to the
> Azure Repo, run Azure Pipelines, or bypass any approval gate.

This procedure provisions Azure resources and incurs cost. Keep the existing
approval boundaries in Sections 1, 7 and 8. A request to prepare or explain
this workflow is not authorization to execute it. Never print, request in chat,
or store credentials or secret values in source, shell output, workflow logs or
artifacts.

### 11.1 Confirm GitHub identity, repository and branch

1. Switch the GitHub CLI to the presenter's existing `imohweb` account and
   verify both the authenticated login and exact repository before any edits
   or API changes:

   ```bash
   gh auth switch --hostname github.com --user imohweb
   gh api user --jq .login
   gh repo view imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines --json nameWithOwner,defaultBranchRef
   ```

   Stop if the login is not `imohweb`, the repository does not match, or
   authentication requires a password/token. Do not ask the presenter to paste
   a credential into chat; ask them to authenticate through GitHub's supported
   sign-in flow and retry.
2. Inspect the checked-out branch, upstream, worktree and all four workflow
   files. Preserve unrelated edits and never stage or commit unrelated files.
   The default deployment branch is `main`, matching the current workflows.
   If the presenter requests a different branch, confirm that exact branch
   before editing and verify the GitHub environment's branch restrictions and
   existing OIDC trust support it. Do not silently relax either protection.

### 11.2 Align workflow branch selection without enabling push deployment

Update and validate
[ci.yml](.github/workflows/ci.yml),
[deploy.yml](.github/workflows/deploy.yml),
[infra.yml](.github/workflows/infra.yml), and
[codeql.yml](.github/workflows/codeql.yml) consistently for the confirmed
target branch:

- CI and CodeQL `push`/`pull_request` branch filters must include the target
  branch. Keep CodeQL's scheduled scan and manual dispatch.
- App release and infrastructure remain `workflow_dispatch` only. Keep their
  explicit branch guards aligned with the target branch and dispatch using
  that branch. **Do not add `push` or `pull_request` triggers to either
  deployment workflow.**
- Preserve all other permissions, approval checks, state checks, and
  concurrency controls. Do not remove the `dev` environment gate or the
  infrastructure workflow's `state_ready` and `apply` inputs.
- Check the YAML and diff before publishing. Do not push merely to test
  deployment workflows. A push to the target branch can run CI and CodeQL,
  but must never deploy infrastructure or the app automatically.

### 11.3 Populate environment variables from verified sources

Inspect the workflow declarations and current Terraform/configuration first.
Use only confirmed values from the existing OIDC service principal, the
intended Azure CLI subscription, approved naming decisions, and successful
Terraform outputs. Never invent IDs, names, prefixes, account names, or
replace a value just to make validation pass. Do not create an
`AZURE_CLIENT_SECRET`; authentication is federated OIDC.

Configure these as **Variables** in GitHub environment `dev` (not repository
variables and not secrets):

| Variable | Source / rule |
| --- | --- |
| `AZURE_CLIENT_ID` | Existing `mmaug_bootcamp_spn_2026` application/client ID used by the GitHub OIDC trust. |
| `AZURE_TENANT_ID` | Tenant ID of the intended Azure subscription; verify with the presenter before use. |
| `AZURE_SUBSCRIPTION_ID` | Confirmed target subscription ID; ensure Azure CLI context matches it. |
| `AZURE_RESOURCE_GROUP` | Exactly `RG-MMAUG-Bootcamp`; it is existing and must not be created or deleted. |
| `STATE_ACCOUNT` | Approved, globally unique 3–24 character lowercase/digit storage account name. Check availability and existing state before selecting. |
| `RESOURCE_PREFIX` | Presenter-approved unique 6–18 character lowercase/digit prefix starting with a letter. |
| `WEB_IDENTITY_RESOURCE_ID` | Full resource ID of the existing administrator-approved user-assigned identity used by both apps; attachment and runtime access must be verified. |
| `FOUNDRY_LOCATION` | Optional; use the approved location (current default is `eastus2`) only after availability/quota review. |
| `ACR_NAME` | Terraform output after successful infrastructure apply. |
| `BACKEND_WEB_APP_NAME` | Terraform output after successful infrastructure apply. |
| `FRONTEND_WEB_APP_NAME` | Terraform output after successful infrastructure apply. |

Use GitHub's environment UI or authenticated `gh variable` commands scoped to
`dev`; do not put values in this file. For a value already verified from an
approved source, the CLI form is:

```bash
gh variable set VARIABLE_NAME --env dev --body "$VERIFIED_VALUE" \
  --repo imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines
```

Set one variable at a time and do not echo the value. Validate required names
against both workflows. The three application outputs are not available until
infrastructure succeeds; set and verify them before app release.

### 11.4 Mandatory presenter pauses

Both infrastructure apply and application release additionally require
`external_access_verified=true` after administrator verification of existing
deployment/runtime/service permissions. This attestation grants no access and
never substitutes for the presenter pauses below.

**Pause A — manual secret entry.** After the non-secret variables have been
verified, stop and ask the presenter to add `SPECIALIST_API_TOKEN` as a
**secret** in the `dev` environment using the settings link above. The
presenter must generate a random value of at least 32 characters and enter it
directly in GitHub; never generate it into chat, read it back, or ask the
presenter to paste it here. Also ask them to configure the required `dev`
environment reviewer and target-branch restrictions if they are absent.
Resume only after the presenter confirms completion. Check secret *presence*
by listing secret names or letting the workflow's non-printing validation
check run; never retrieve or display a secret value.

**Pause B — infrastructure review and authorization.** Before running the
infrastructure workflow, show the presenter the target branch/commit,
subscription, resource group, state account/container, whether state is
existing or has been reconciled, and the Terraform plan's additions,
changes, replacements, and deletions. The plan workflow bootstraps Blob Storage
before Terraform init, so even `apply=false` can create billable storage.
Require explicit confirmation to proceed with that side effect and a separate
clear approval to apply the reviewed saved plan. Do not set `state_ready=true`
unless prior state has actually been reviewed/migrated or the presenter
confirms a reviewed new deployment. Do not dispatch apply if the plan includes
unapproved deletion/replacement, wrong scope, missing role setup, or uncertain
state. The GitHub environment's required reviewer must approve the protected
apply job. Never run `terraform apply` locally as a workaround.

**Pause C — application release.** After infrastructure succeeds, review the
Terraform outputs and populate the three app-release variables. Confirm the
exact source commit, successful CI and CodeQL results for that commit, and
the frontend/backend deployment targets. Ask for explicit approval immediately
before manually dispatching `deploy.yml`; do not auto-dispatch it after
infrastructure. Deployment builds/pushes images and changes both App Services.

### 11.5 Execute and verify in this order

1. Confirm the four workflow files are aligned with the target branch. Commit
   and push only the reviewed, task-related changes to the GitHub repository
   after presenter approval. Pushing to GitHub may run CI and CodeQL; it must
   not deploy. Do not push these changes to the Azure Repo.
2. Run CI and CodeQL for the exact target-branch commit, using normal
   push-triggered runs or their manual dispatch. Wait for completion and
   inspect results. Do not continue with failing or cancelled required checks.
3. Perform Pause A and Pause B. Run the GitHub `infra.yml` workflow on the
   target branch with `state_ready=true` only after state review and
   `apply=true` only after the plan review and explicit authorization. Wait
   for administrator verification of all existing access before confirming
   `external_access_verified=true`; this does not replace the plan approval. Wait
   for the environment reviewer approval and successful Terraform apply.
   Do not assume a successful bootstrap or plan means infrastructure applied.
4. Populate `ACR_NAME`, `BACKEND_WEB_APP_NAME` and
   `FRONTEND_WEB_APP_NAME` from the successful Terraform outputs. Verify every
   required environment variable and `SPECIALIST_API_TOKEN` presence without
   exposing the secret. Perform Pause C, then manually dispatch `deploy.yml`
   on the target branch.
5. Wait for the release workflow and both App Service health checks. Verify
   the React shell and API health endpoint, then test a synthetic support
   ticket end to end: draft remains hidden from the customer until a specialist
   approves it, and only the approved response is returned. Do not use real
   customer data.
6. If a workflow fails, stop at the failing stage. Inspect the specific
   GitHub Actions job logs and safe diagnostics; redact any accidentally
   exposed values and never dump tokens, secrets, Terraform state or plan JSON.
   Fix the root cause, rerun only the necessary checks, and request approval
   again before any repeated infrastructure apply or app release. Do not
   broaden permissions, bypass environment protection, deploy through Azure
   Pipelines, or roll back without presenter authorization.

If GitHub authentication, an OIDC trust, reviewer protection, state history,
Azure role assignment, plan contents, deployment health, or required input is
unclear, stop and ask the presenter. Do not guess or silently continue.
