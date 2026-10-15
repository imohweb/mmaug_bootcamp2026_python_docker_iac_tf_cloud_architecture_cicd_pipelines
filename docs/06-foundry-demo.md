# Optional instructor demo: Foundry agent + Azure OpenAI + App Service

This is a paid, opt-in extension to the existing local Python/Docker lab.
It demonstrates two **different** application integrations:

| Request | Python SDK | What happens |
| --- | --- | --- |
| `POST /ai/model` | `openai.AzureOpenAI` | Calls an Azure OpenAI model deployment directly using chat completions |
| `POST /ai/agent` | `azure.ai.projects.AIProjectClient` | Gets an agent-bound OpenAI client and calls Responses using the deployed prompt agent |

The current Foundry Agent Service SDK surface is in **azure-ai-projects 2.x**.
This is not the classic hub/project or classic threads/runs example from the
older `azure-ai-agents` SDK. The pinned versions are in
[requirements](../launchpad-lab/requirements.txt). The model **deployment name**,
not the catalog model name, is passed to inference and the agent definition.
Agent creation happens during Terraform apply, **not** on every HTTP request.

## 1. Authentication and local placeholders

From the repository root, use a Bash/zsh terminal:

```bash
cd launchpad-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
# Only if .env-local does not already exist:
cp -n .env-local.example .env-local
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the generated token in `AI_DEMO_API_TOKEN` in `.env-local`. It must be
at least 32 characters and must not be a placeholder. Do not project real
credentials during the presentation. `app.py` loads this file automatically
without overriding existing process environment values.

| Setting | Fill with |
| --- | --- |
| `FOUNDRY_PROJECT_ENDPOINT` | Terraform `foundry_project_endpoint` |
| `FOUNDRY_AGENT_NAME` | Terraform `foundry_agent_name` |
| `AZURE_OPENAI_ENDPOINT` | Terraform `azure_openai_endpoint` |
| `AZURE_OPENAI_DEPLOYMENT` | Terraform `azure_openai_deployment` |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` for this chat-completions example |
| `AI_DEMO_API_TOKEN` | Random instructor demo bearer token |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Optional service-principal credentials; leave blank when using `az login` or the system identity |
| `AZURE_OPENAI_API_KEY` | Optional key auth for a separately configured key-enabled endpoint; leave blank for this lab |

The default agent name is `mmaug-launchpad-tutor`. The configured model is
**GPT-4.1-mini**, version **`2025-04-14`**, deployed as `demo-model` with
`GlobalStandard`. It is not GPT-5.4 or GPT-6. Changing the agent name does not
change the underlying model. These are configuration defaults, not evidence
that an Azure deployment has already occurred.

There are **no Azure passwords or API keys required** in the recommended path.
`DefaultAzureCredential` uses your local Azure CLI identity and App Service's
system-assigned identity in Azure. Terraform disables Foundry local/key
authentication. The OpenAI SDK requests an Entra token for
`https://cognitiveservices.azure.com/.default`; Foundry project authentication is
handled by its SDK.

`.env-local` is excluded from Git and Docker's build context. Commit only
`.env-local.example`, never a populated local file. Do not set `AZURE_CLIENT_ID`
to the system-assigned identity's ID; it is only needed for a deliberately
configured service principal or user-assigned identity.

## 2. Provision the infrastructure deliberately

The existing Terraform already deploys a Linux App Service plan/web app, ACR
with admin credentials disabled, an App Service system identity with `AcrPull`,
and a VM/Nginx comparison target. This extension preserves that architecture;
it is **not** an App-Service-only root. Budget for the VM too. It adds:

- Foundry `AIServices` account with project management enabled;
- a new-style `Microsoft.CognitiveServices/accounts/projects` project;
- an Azure OpenAI model deployment;
- a dedicated prompt agent, created using the SDK;
- runtime project access (`Azure AI User`), account model inference
  (`Cognitive Services OpenAI User`), and project-identity inference access.

Use an approved subscription and unique `prefix`. The deployer needs resource
creation rights **and** role-assignment rights. Contributor alone cannot assign
roles. It must also be allowed to receive/use the assigned `Azure AI User`
data-plane role. Azure Policy, model access, regional capacity and quota still
apply. Do not silently switch regions/models if quota is unavailable.

```bash
# From launchpad-lab, with .venv activated:
az login
export ARM_SUBSCRIPTION_ID="YOUR_APPROVED_SUBSCRIPTION_ID"
az account set --subscription "$ARM_SUBSCRIPTION_ID"
az account show --query '{name:name,id:id}' -o table
az provider register --namespace Microsoft.CognitiveServices --wait
# Also complete the existing Web/Compute/Network/ACR provider registrations
# and SSH-public-key setup in docs/03-terraform-azure.md.
export TF_VAR_agent_python_executable="$(command -v python)"
cd ../infra/azure
cp -n terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: real subscription_id, globally unique prefix,
# location, existing SSH PUBLIC key, and enable_foundry = true.
# Verify foundry_location, model_name/version/SKU and model_capacity.
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=foundry.tfplan
# Review billable resources, public endpoints, identities and role scopes.
# Only after approval:
terraform apply foundry.tfplan
terraform output foundry_project_endpoint
terraform output azure_openai_endpoint
terraform output azure_openai_deployment
terraform output foundry_agent_name
```

The defaults illustrate `gpt-4.1-mini`, version `2025-04-14`, `GlobalStandard`,
capacity 10, in `eastus2`. They are **not a guarantee of availability** or a
price quote. Confirm model lifecycle, regional Agent Service availability,
quota and data-residency requirements before applying; GlobalStandard can
process requests globally. Choose an appropriate supported SKU for residency.

**Terraform/SDK boundary:** `foundry.tf` uses AzAPI for account/project and
AzureRM for model/RBAC. `terraform_data.agent` calls
`launchpad-lab/manage_agent.py` with the active Python environment. SDK
dependencies and data-plane authentication must be available on the machine
running **apply and destroy**. Use the same Entra principal for Azure CLI and
Terraform; if deliberately using a service principal, configure both providers
and `DefaultAzureCredential` for that principal.

This is a teaching bridge, not a native drift-aware agent Terraform provider.
It checks whether a matching agent already exists before creating one and fails
on conflicting definitions. Terraform does not continuously refresh remote
agent definitions. Instructions/name/model/script changes replace the bridge:
the old dedicated agent is deleted before recreation. Destroy deletes that
agent while project/model/RBAC still exist. Do not use a shared or manually
managed agent name. Keep the local script and Python environment available for
destroy. If an apply fails after data-plane creation, inspect the agent and
Terraform state before retrying; never discard state as a repair.

The bridge logs and retries 403 responses briefly for RBAC propagation, then
fails explicitly. A persistent 403 needs role/identity diagnosis, not wider
credentials. Runtime roles may take additional time to propagate.

## 3. Run the Python application and demonstrate both SDKs

Copy the four Terraform output values into `.env-local`, then:

```bash
cd ../../launchpad-lab
python app.py
```

In a second terminal, from `launchpad-lab` (activate `.venv` first):

```bash
# Export values without sourcing arbitrary shell code from a dotenv file:
export AI_DEMO_API_TOKEN="$(python -c 'from dotenv import dotenv_values; print(dotenv_values(".env-local")["AI_DEMO_API_TOKEN"])')"
export BASE_URL="http://127.0.0.1:8000"
curl -fsS "$BASE_URL/health"
curl -fsS "$BASE_URL/sum?values=5,10,15"
curl -fsS "$BASE_URL/ai/model" \
  -H "Authorization: Bearer $AI_DEMO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain a Docker image versus a container in three sentences."}'
curl -fsS "$BASE_URL/ai/agent" \
  -H "Authorization: Bearer $AI_DEMO_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain how Terraform, ACR and App Service work together."}'
```

Expected shape: `{"mode":"model","answer":"..."}` or
`{"mode":"agent","answer":"..."}`. Generated text is nondeterministic.
Missing/wrong token returns 401; an unconfigured demo returns 503; invalid JSON
or prompts return 400; a body over 16 KiB returns 413. Azure/SDK errors produce
502 with server-side diagnostics, not a fabricated successful answer.
Prompts are limited to 2000 characters and output to 300 tokens. Requests use
bounded timeouts and no automatic OpenAI retries. Keep prompts small.

Read `ai_demo.py` while presenting: direct `AzureOpenAI` authentication,
`chat.completions.create`, project client, agent-bound `get_openai_client`,
and `responses.create`. This demo uses no tools, RAG, shared conversation,
or browser AI UI. Agent instructions live in Foundry; direct-model system
instructions live in application code. No agent is created per request.

## 4. Docker Desktop: build locally, run locally, then push to ACR

Start Docker Desktop with Linux containers and verify `docker info`. These
commands do a **local Docker build**, not `az acr build`. From repository root:

```bash
docker version
docker info
export IMAGE_TAG="demo-$(date -u +%Y%m%d%H%M%S)"
docker build --platform linux/amd64 \
  -t "mmaug-launchpad:$IMAGE_TAG" ./launchpad-lab
docker run -d --name mmaug-foundry-local \
  -p 127.0.0.1:8082:8000 \
  -e APP_MESSAGE="Hello from the local Docker image!" \
  "mmaug-launchpad:$IMAGE_TAG"
curl -fsS http://127.0.0.1:8082/health
curl -fsS "http://127.0.0.1:8082/sum?values=5,10,15"
docker logs mmaug-foundry-local
docker inspect --format '{{.State.Health.Status}}' mmaug-foundry-local
docker stop mmaug-foundry-local
docker rm mmaug-foundry-local
```

Wait for health to become `healthy`; inspect logs if startup fails. Use
`linux/amd64` for Azure even on Apple Silicon. Configuration and credentials
are not baked into the image. This local container intentionally tests the
unchanged API, **not Azure AI authentication**: it has neither Azure CLI nor
App Service's identity endpoint. For optional AI-in-container testing, an
approved service principal can be passed at runtime with `--env-file
launchpad-lab/.env-local`, but that exposes credentials to container inspection;
prefer host-side `az login` for this demo. Never mount your home credentials
directory or bake CLI tokens into the image.

```bash
# From repository root, retaining IMAGE_TAG:
export ACR_NAME="$(terraform -chdir=infra/azure output -raw acr_name)"
export ACR_SERVER="$(terraform -chdir=infra/azure output -raw acr_login_server)"
export RG="$(terraform -chdir=infra/azure output -raw resource_group_name)"
export WEB_APP="$(terraform -chdir=infra/azure output -raw web_app_name)"
# One-time admin action if the publishing identity does not already have AcrPush:
export PUBLISHER_OBJECT_ID="$(az ad signed-in-user show --query id -o tsv)"
export ACR_ID="$(az acr show -g "$RG" -n "$ACR_NAME" --query id -o tsv)"
az role assignment create --assignee-object-id "$PUBLISHER_OBJECT_ID" \
  --assignee-principal-type User --role AcrPush --scope "$ACR_ID" -o none
# Allow role propagation, then authenticate Docker using your Azure CLI identity.
az acr login --name "$ACR_NAME"
docker tag "mmaug-launchpad:$IMAGE_TAG" "$ACR_SERVER/launchpad:$IMAGE_TAG"
docker push "$ACR_SERVER/launchpad:$IMAGE_TAG"
export IMAGE_DIGEST="$(az acr repository show \
  --name "$ACR_NAME" --image "launchpad:$IMAGE_TAG" --query digest -o tsv)"
export IMAGE_REF="$ACR_SERVER/launchpad@$IMAGE_DIGEST"
printf 'Release image: %s\n' "$IMAGE_REF"
```

For a service-principal publisher, use its **object ID**, not app/client ID,
and `--assignee-principal-type ServicePrincipal`. Do not enable ACR's admin
account. Stop if publishing fails; do not deploy a fallback image/tag.

## 5. App Service consumes that exact image

Terraform configured `container_registry_use_managed_identity = true` and
`AcrPull` for the web app identity. The human publisher uses `AcrPush`;
the web app does not need publishing privileges.

```bash
# Same shell as section 4. AI_DEMO_API_TOKEN must be the random demo token.
# Load it from your local dotenv file if this is a different shell:
export AI_DEMO_API_TOKEN="$(launchpad-lab/.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values("launchpad-lab/.env-local")["AI_DEMO_API_TOKEN"])')"
az webapp config set -g "$RG" -n "$WEB_APP" \
  --linux-fx-version "DOCKER|$IMAGE_REF" -o none
az webapp config appsettings set -g "$RG" -n "$WEB_APP" \
  --settings "AI_DEMO_API_TOKEN=$AI_DEMO_API_TOKEN" -o none
az webapp restart -g "$RG" -n "$WEB_APP"
export BASE_URL="$(terraform -chdir=infra/azure output -raw web_app_url)"
curl --retry 12 --retry-delay 10 --retry-all-errors --fail "$BASE_URL/health"
curl -fsS "$BASE_URL/sum?values=5,10,15"
# Repeat the two AI curl requests from section 3 with this BASE_URL.
az webapp config show -g "$RG" -n "$WEB_APP" \
  --query linuxFxVersion -o tsv
```

Check that the configured image matches `IMAGE_REF`, health returns `ok`,
sum returns 30/10.0, and **both** protected AI requests return an answer.
Health alone does not test Azure AI permissions. If the image cannot pull,
inspect App Service container logs, ACR identity permissions and role
propagation. A 502 from an AI route needs application logs, endpoint/deployment
checks, identity roles, quota and model availability checks.

Terraform intentionally leaves image releases and the instructor demo token
under external management. Other app settings are Terraform-owned. Do not
enable the demo token through a public pipeline variable. App settings and
Terraform refresh/state may contain sensitive values: protect state, restrict
reader access and use approved secret-management controls for real workloads.

The bearer token is a **classroom access guard, not production user auth**.
There is no per-user authorization, rate limiting or complete abuse protection.
Use HTTPS for cloud requests, keep the token private, do not send sensitive
participant data, and rotate/unset the token after the demo. The HTTP-only VM
does not receive AI credentials/configuration and is not an AI demo target.

## 6. Cleanup and costs

App Service plan, ACR, VM and model usage can incur charges. Stopping the web app
does not stop plan/storage charges. Review cost estimates and budgets first.
To disable the public AI routes without deleting infrastructure:

```bash
az webapp config appsettings delete -g "$RG" -n "$WEB_APP" \
  --setting-names AI_DEMO_API_TOKEN -o none
```

For full teardown, activate the SDK environment, authenticate as the deployer,
retain the same Terraform inputs and review the destruction plan:

```bash
terraform -chdir=infra/azure plan -destroy -out=cleanup.tfplan
# Review: all resources in THIS root, including the existing VM, will be removed.
terraform -chdir=infra/azure apply cleanup.tfplan
docker image rm "mmaug-launchpad:$IMAGE_TAG" "$ACR_SERVER/launchpad:$IMAGE_TAG"
unset AI_DEMO_API_TOKEN
```

Do not delete state first. The agent destroy bridge requires network access,
SDKs and a data-plane role; failures are explicit and must be resolved before
retrying cleanup. Any manually added publisher role is scoped to the registry
and disappears with that registry. No Azure deployment is claimed merely
because local schema validation or mocked SDK tests pass.

## Official references

- [Foundry prompt-agent quickstart](https://learn.microsoft.com/azure/foundry/agents/quickstarts/prompt-agent)
- [AI Projects Python SDK](https://pypi.org/project/azure-ai-projects/)
- [OpenAI Python SDK](https://pypi.org/project/openai/)
- [Foundry account/project ARM and Terraform reference](https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts/projects)
- [App Service managed-identity image pulls](https://learn.microsoft.com/azure/app-service/configure-custom-container)
- [ACR Docker push/pull](https://learn.microsoft.com/azure/container-registry/container-registry-get-started-docker-cli)
