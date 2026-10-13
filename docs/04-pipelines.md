# 04 — Two pipelines, one immutable Docker image

## Session progression

On **17 October 2026**, use this guide to introduce the build/test/release
handoff. On **27 October 2026**, return to the same files for **Advanced Cloud
Architecture & DevOps CI/CD Pipeline Process**: examine hosting trade-offs,
federated trust, scoped permissions, artifact identity, environment approvals,
runtime verification and recovery.

The app and shared deployment scripts do not change merely because the session
is more advanced. Choose one orchestrator at a time, and distinguish the
implemented demo from production controls that remain to be added.

## What you will build

GitHub Actions and Azure DevOps are **alternative release orchestrators** for the same repository. Both test the Python app, build the `launchpad-lab/Dockerfile` for `linux/amd64`, push `launchpad` to Azure Container Registry (ACR), resolve its SHA-256 digest, and deploy that **exact digest** to:

1. Linux App Service, using its managed identity to pull the container.
2. An Ubuntu VM, using its managed identity to pull the container, with nginx forwarding public port 80 to `127.0.0.1:8000`.

The VM's container listens on port 8000 but is published only on loopback. No public SSH is needed: Azure VM Run Command executes the guest deployment script as root. HTTP on the VM is a **demo shortcut**, not production transport security.

```text
tests → build once → ACR launchpad:commit-run-attempt
                       ↓ resolve sha256 digest
                ┌──────┴───────┐
           App Service      Ubuntu VM
              HTTPS         HTTP → nginx → container
```

Do not run both orchestrators against the same targets at once. GitHub's concurrency lock does not lock Azure DevOps, and two different release digests can overwrite each other's deployments. Stop one pipeline before using the other.

## Prerequisites: infrastructure first

Provision `infra/azure` using the infrastructure lesson. Pipelines do **not** create infrastructure or assign roles. Wait for VM cloud-init to finish installing Docker, nginx, curl, and Azure CLI, and enabling Docker/nginx.

Infrastructure outputs map to pipeline variables:

| Terraform output | Variable |
| --- | --- |
| `resource_group_name` | `AZURE_RESOURCE_GROUP` |
| `acr_name` | `ACR_NAME` |
| `web_app_name` | `AZURE_WEB_APP_NAME` |
| `vm_name` | `AZURE_VM_NAME` |
| `vm_public_ip` | optional `VM_PUBLIC_IP` (GitHub/manual use) |
| `acr_login_server` | queried by each build; no variable needed |
| `web_app_url` | useful for visiting the app; script queries the hostname |

Use the subscription ID of those resources as `AZURE_SUBSCRIPTION_ID`. Registry admin access stays **disabled**. This sample uses ACR's `LegacyRegistryPermissions` RBAC mode, not repository ABAC.

### Identities and permissions

Keep the **pipeline identity**, the **App Service identity**, and the **VM identity** separate:

| Identity | Demo role / scope | Why |
| --- | --- | --- |
| GitHub federated app/service principal | `Contributor` on the demo resource group | Update App Service and invoke VM Run Command |
| Azure DevOps federated service connection identity | same demo RG `Contributor` | Same deployment operations |
| Each pipeline identity | `AcrPush` on this ACR | Push layers and read image digest |
| App Service system-assigned identity | `AcrPull` on this ACR | Platform pulls the image |
| VM system-assigned identity | `AcrPull` on this ACR | Guest pulls the image |

The infrastructure grants the last two roles. An administrator with role-assignment permissions configures the pipeline roles **outside** these workflows. Contributor does not grant role-assignment permissions. Do not grant Owner or subscription-wide Contributor just to run this demo.

RG Contributor is a beginner-friendly but broad permission. VM Run Command is **privileged root execution**. Production should narrow scopes/custom roles to web app read/config write/restart/log actions, VM read/`Microsoft.Compute/virtualMachines/runCommand/action`, and network-interface/public-IP reads for address lookup, with ACR push/read permissions confined to the registry. Protect workflow/script changes with review; approval is not a substitute for reading what will execute.

## GitHub Actions setup

1. In repository **Settings → Environments**, create `azure-demo`. Configure required reviewers, prevent self-review when available, and restrict deployments to `main`. These checks are configured in GitHub, not by YAML.
2. Create an Entra app/service principal (or a dedicated supported federated identity). Add a federated credential with:
   - issuer: `https://token.actions.githubusercontent.com`
   - audience: `api://AzureADTokenExchange`
   - subject: `repo:imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines:environment:azure-demo`
3. Assign the pipeline roles above. For a fork or renamed repository, replace the owner/repository part of the subject exactly.
4. Add these **environment variables** to `azure-demo`:

| Variable | Value |
| --- | --- |
| `AZURE_CLIENT_ID` | federated Entra application's client ID |
| `AZURE_TENANT_ID` | tenant ID |
| `AZURE_SUBSCRIPTION_ID` | subscription GUID |
| `AZURE_RESOURCE_GROUP` | output `resource_group_name` |
| `ACR_NAME` | output `acr_name`, not the login hostname |
| `AZURE_WEB_APP_NAME` | output `web_app_name` |
| `AZURE_VM_NAME` | output `vm_name` |
| `VM_PUBLIC_IP` | optional single public IPv4; omit to query the VM |

No `AZURE_CLIENT_SECRET`, registry password, SSH key, or publish profile is used. IDs and resource names are configuration, not authentication secrets.

### Existing federation after the repository rename

The repository now uses the name
`mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines`.
GitHub URL redirects do not update Microsoft Entra federated credentials.
If you configured trust using the former name, update that credential's
repository subject to the exact value above before deploying. Keep issuer,
audience and the protected environment aligned with the workflow. Remove stale
trust for the former repository name after verifying the replacement.

The Azure identity and its client ID can remain the same; changing the repository
name does not require a client secret or broader permissions. Review GitHub
environment variables, deployment restrictions and any external Azure DevOps
repository connection as well. These external settings are not changed by
editing this guide.

### Files and execution order

- [CI workflow](../.github/workflows/ci.yml): push/PR to `main`, or manual. Runs Python 3.10/3.12 HTTP tests and Terraform 1.16.5 `fmt -check`, backend-disabled `init`, and `validate` for both Terraform roots. It does not sign in to Azure, plan, apply, or deploy.
- [Deployment workflow](../.github/workflows/deploy.yml): **manual dispatch only**, `main` only. First runs the Python 3.12 tests; then `release` waits for the `azure-demo` environment approval.
- `azure/login` exchanges a GitHub OIDC token for short-lived Azure credentials. `id-token: write` is granted only to the release job.
- The tag combines full commit SHA, GitHub run ID, and run attempt. After push, `az acr repository show` returns the digest. The job writes `IMAGE_REF=registry.azurecr.io/launchpad@sha256:…` to `$GITHUB_ENV`, then calls the shared script.

Open **Actions → Deploy Azure demo → Run workflow → main**, review the tested commit and permissions, approve the environment, and follow the release logs. Pushes and pull requests never deploy. This manual workflow retests the checked-out commit but does not wait for CodeQL; see the next lesson for scan/gate distinctions.

## Azure DevOps setup

1. Import/connect this repository in Azure DevOps. Create a pipeline using [pipelines/azure-pipelines.yml](../pipelines/azure-pipelines.yml), not a generated starter YAML.
2. Under **Project settings → Service connections**, create an **Azure Resource Manager** connection using **workload identity federation**. Name it `azure-demo-wif` (or override the `azureServiceConnection` parameter).
   - Automatic creation is convenient if the setup administrator has the required Azure permissions.
   - For manual federation, use the issuer and subject **shown by Azure DevOps** when creating the connection. Add those exact values to the Entra identity's federated credential, then verify/save. Do not reuse GitHub's federation subject or invent a service-connection subject.
   - Grant the connection identity the RG/ACR roles above. Authorize only this pipeline; do not select grant access to all pipelines.
3. Under **Pipelines → Environments**, create `azure-demo`, and configure an **Approvals and checks** approval with a reviewer. Configure branch control to allow `refs/heads/main`. Add an exclusive lock if you permit multiple runs; queue/review releases deliberately.
4. Set these pipeline UI variables: `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `ACR_NAME`, `AZURE_WEB_APP_NAME`, `AZURE_VM_NAME`. They are non-secret configuration. Authentication belongs to the federated service connection. This pipeline always queries the VM's actual public IP.
5. Run the pipeline on `main` with parameter `deploy: true`. The default `false` runs tests only, including on ordinary CI pushes/PRs.

The stages are **Test → Build → Deploy**. `AzureCLI@2` authenticates through the WIF service connection, without exposing service-principal tokens to the script. Build pushes one image and emits:

```text
##vso[task.setvariable variable=imageRef;isOutput=true]registry/launchpad@sha256:…
```

The named step `publishImage` in job `BuildImage` exports that value. Deploy reads it using:

```yaml
IMAGE_REF: $[ stageDependencies.Build.BuildImage.outputs['publishImage.imageRef'] ]
```

This is a **cross-stage output**, not a local shell variable or an artifact guessed from `latest`. The deployment job waits for `azure-demo` approval, checks out the same source version, and invokes `scripts/deploy-azure.sh` via `AzureCLI@2`. Both Build and Deploy require `main` and `deploy: true`; PR code cannot deploy.

YAML `pr` triggers apply when the repository provider supports them (including GitHub). For Azure Repos Git, configure a branch-policy build-validation rule instead. Azure DevOps tests Python 3.12; the GitHub CI workflow provides the 3.10/3.12 matrix and Terraform checks.

## Shared scripts: exact manual interface

[scripts/deploy-azure.sh](../scripts/deploy-azure.sh) runs on a **Linux runner** with Bash, Azure CLI, `curl`, `jq`, and GNU `timeout`. Authenticate beforehand (`az login` interactively for local manual use, OIDC/WIF in pipelines). It accepts **environment variables**, not positional arguments:

| Name | Required? | Format |
| --- | --- | --- |
| `AZURE_SUBSCRIPTION_ID` | yes | subscription GUID |
| `AZURE_RESOURCE_GROUP` | yes | existing demo resource group |
| `ACR_NAME` | yes | alphanumeric ACR name |
| `AZURE_WEB_APP_NAME` | yes | existing Linux custom-container app |
| `AZURE_VM_NAME` | yes | existing Ubuntu VM |
| `IMAGE_REF` | yes | `<acr>.azurecr.io/launchpad@sha256:<64 lowercase hex>` |
| `VM_PUBLIC_IP` | no | one IPv4 address; omitted/empty means query Azure |

```bash
# On a Linux shell, after az login; substitute your actual outputs and digest.
export AZURE_SUBSCRIPTION_ID="00000000-0000-0000-0000-000000000000"
export AZURE_RESOURCE_GROUP="your-demo-rg"
export ACR_NAME="yourregistry"
export AZURE_WEB_APP_NAME="your-web-app"
export AZURE_VM_NAME="your-vm"
export IMAGE_REF="yourregistry.azurecr.io/launchpad@sha256:<actual-64-hex-digest>"
bash scripts/deploy-azure.sh
```

The placeholder digest is intentionally invalid: use the real pushed digest. Obtain it with `az acr repository show --name "$ACR_NAME" --image "launchpad:<your-tag>" --query digest --output tsv`. The scripts reject tags, another repository/registry, shell metacharacters, and invalid required configuration before deploying.

[scripts/deploy-vm.sh](../scripts/deploy-vm.sh) is the **guest script**, not a second runner-side deployment entry point. Its positional arguments are `$1 = IMAGE_REF`, `$2 = ACR_NAME`. The orchestrator supplies named Run Command parameters `imageRef=…`, `acrName=…` in that order; the Linux handler passes their values positionally. No other configuration variables are required in the guest. Run Command runs as root; `az login --identity` uses the VM's own identity. `az acr login` acquires a short-lived registry credential, never an admin password; Docker caches that credential in the guest's root Docker configuration.

The orchestrator configures App Service's managed-identity pull, `WEBSITES_PORT=8000`, container filesystem logging, and the digest using current `--container-image-name`/`--container-registry-url` flags; then restarts it. It uses neither deprecated `--docker-custom-image-name` nor registry password flags.

The guest pulls **before removing** the old container, replaces only the container named `launchpad`, and starts the new container with `--restart unless-stopped`. This simple replacement creates brief downtime; it is not a rolling or transactional deployment. If one target fails, the other may already have changed. Correct the failure and redeploy, or explicitly rerun with a previously successful digest for rollback. Terraform ignores the release image field so later infrastructure applies do not undo a pipeline release.

## Verification and failures

- Visit App Service `https://<hostname>/ui` and VM `http://<public-ip>/ui`.
- Both **public endpoints** must return a JSON object with `/health` status `"ok"` and `/sum?values=5,10,15` numeric `total: 30` and numeric `average: 10`. Invalid/non-JSON payloads, missing fields, wrong values, and string `"10"` fail immediately and visibly, preserving the target's diagnostic-log path. Successful health alone is not sufficient. The guest's separate localhost check verifies nginx health before emitting its marker; the runner performs the strict JSON health-and-sum assertions on both Azure targets.
- Startup is the **only** retried operation: up to 30 attempts, 5-second waits and 10-second request limits on the runner; 2-second waits and 5-second request limits in the guest. Authorization, build, push, and configuration failures stop immediately.
- Failed App Service readiness prints a bounded 30-second log stream. Failed guest readiness prints the last 100 container-log lines and 30 nginx journal lines. Failed public VM readiness also retrieves guest diagnostics.
- VM Run Command can report Azure provisioning success even when a shell command failed. The runner inspects guest messages and any returned exit codes and requires an exact digest-specific `LAUNCHPAD_DEPLOY_OK_<digest-hex>` line, emitted only after nginx/local health succeeds. A missing marker fails deployment.
- Health and sum checks confirm availability/application behavior, not a build-version attestation. The VM additionally checks the running container's configured image digest; App Service applies the digest configuration but these endpoints do not identify the serving release.
- `403`/image-pull failures: check **which identity** needs `AcrPush` vs `AcrPull`, correct scopes, and RBAC propagation. App Service managed-identity pulls need ACR ARM-audience authentication enabled (the default).
- Missing VM prerequisites: inspect cloud-init completion; do not mask a failed bootstrap with repeated deployments. Public VM readiness requires HTTP 80 ingress; SSH and container port 8000 remain closed.

### Offline deployment regression tests

From the repository root, run `bash tests/test-deploy.sh` (requires Bash and `jq`). The persistent harness mocks Azure CLI, curl, Docker, service checks, sleep, and timeout; it makes **no live Azure, HTTP, or Docker calls**. It retains the original 12 success/failure scenarios and adds malformed/wrong health and sum JSON cases independently for App Service and the VM, for 38 scenarios total, including empty bodies, numeric strings, and multiple concatenated JSON objects. The guest root guard is bypassed only in the in-memory test copy; production scripts remain unchanged. GitHub CI runs this harness in its own offline job.

### References

- [Azure login action / OIDC](https://github.com/Azure/login)
- [App Service custom containers and managed identity](https://learn.microsoft.com/azure/app-service/configure-custom-container?pivots=container-linux)
- [Current container configuration CLI](https://learn.microsoft.com/cli/azure/webapp/config/container?view=azure-cli-latest)
- [Linux VM Run Command](https://learn.microsoft.com/azure/virtual-machines/linux/run-command)
- [Azure DevOps workload identity service connections](https://learn.microsoft.com/azure/devops/pipelines/library/connect-to-azure?view=azure-devops)
- [Azure DevOps approvals/checks](https://learn.microsoft.com/azure/devops/pipelines/process/approvals?view=azure-devops)
- [Cross-stage output variables](https://learn.microsoft.com/azure/devops/pipelines/process/set-variables-scripts?view=azure-devops)
