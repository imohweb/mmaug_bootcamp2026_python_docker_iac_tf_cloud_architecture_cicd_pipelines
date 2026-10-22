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
2. Terraform role assignments need a scoped RBAC administration role, ideally
   constrained to the role definitions/principals the app actually needs.
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
3. Run bootstrap before `terraform init`: create/reuse Entra-only StorageV2 and
   the three containers, without managing that storage in the app root module.
4. Initialize the Azure backend with OIDC and the private state container.
5. Validate and create the plan. Protect saved plans as sensitive artifacts.
6. Review the exact plan and its commit. Apply that plan only after the intended
   approval boundary; do not re-plan silently after approval.
7. Verify knowledge indexing and agent retrieval setup. An accepted indexer
   start request is not equivalent to successful ingestion.
8. Record outputs for application release variables. Do not print secrets or
   automatically trigger deployment before infrastructure is ready.

Azure Pipelines currently provides application delivery only. GitHub federation
does not create Azure DevOps WIF trust; configure its service connection
separately if using that alternative.

## 9. Application release procedure

Pushes to `main` can trigger automatic application release after successful CI.
Do not push merely to test a document. Manual dispatch of
[deploy.yml](.github/workflows/deploy.yml) also needs release authorization and
reviewed CI evidence for that commit.

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
