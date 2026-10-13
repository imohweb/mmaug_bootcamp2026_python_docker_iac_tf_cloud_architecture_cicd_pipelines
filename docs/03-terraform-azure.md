# Terraform: from local initiation to Azure modules and remote state

## Session placement

**17 October:** teach the local Docker Terraform workflow, resource lifecycle,
plans, module concepts and state fundamentals. The later Azure examples remain
available for explanation/reference without requiring a cloud deployment.

**27 October:** use the Azure modules to compare hosting architectures, examine
collaborative state/migration/import, and establish the infrastructure
prerequisites for the [advanced pipeline workshop](04-pipelines.md). Detailed
release configuration and [DevSecOps exercises](05-devsecops-codeql.md) belong
to that session. Keep infrastructure ownership separate from image-release
ownership.

## 1. Mental model and local Docker lab

HCL declares desired resource attributes. A provider talks to the resource API.
State maps a Terraform address to an actual resource identity. A plan compares
intent and refreshed managed resources; apply executes the reviewed actions.
Terraform is **not** a continuously running drift-repair controller.

From `launchpad-lab`, build `mmaug-launchpad:1.0` and remove the manual container
first. The local Docker root intentionally keeps the initial exercise small.

```bash
cd terraform
export DOCKER_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
terraform init
terraform fmt -check
terraform validate
terraform plan -out=launchpad.tfplan
# Read the plan: fresh state expects 2 to add.
terraform apply launchpad.tfplan
terraform output -raw app_url
curl -fsS http://127.0.0.1:8080/health
terraform state list
terraform plan
```

PowerShell endpoint selection:

```powershell
$env:DOCKER_HOST = docker context inspect --format '{{.Endpoints.docker.Host}}'
```

- `init`: initializes working directory, modules, provider and backend.
- `fmt`: canonical formatting, not a logical proof.
- `validate`: HCL/types/provider schema, not daemon or application health.
- `plan`: proposed actions; `+` create, `~` update, `-/+` replace, `-` destroy.
- `apply saved.tfplan`: executes the saved plan **without another approval prompt**.
  Review and approve before issuing this command.
- `output`: reads useful values, not a readiness test.
- `state list`: shows managed addresses without dumping potentially sensitive state.
- `.terraform.lock.hcl`: selected provider versions/checksums; commit it.
- `.terraform/`: downloaded working data; do not commit it.

```bash
terraform plan -var="host_port=8081" -out=change.tfplan
# Expect container replacement; read the actual plan.
terraform apply change.tfplan
curl -fsS http://127.0.0.1:8081/health
terraform plan -var="host_port=8081"
terraform plan -destroy -var="host_port=8081" -out=cleanup.tfplan
# Review only the two lab resources.
terraform apply cleanup.tfplan
cd ..
docker image rm mmaug-launchpad:1.0
```

Keep overrides consistent or intentionally change the source default. The image
remains during destroy because `keep_locally = true`. Source edits do not
rebuild that image automatically. Never delete state first.

## 2. What is a module?

Every directory of `.tf` files used together is a module. The directory where
you execute Terraform is the **root module**. A `module` block calls a **child
module**. Files such as `main.tf`, `variables.tf`, and `outputs.tf` are conventions;
Terraform combines all `.tf` files in that directory.

```hcl
module "web" {
  source              = "./modules/web"
  name                = "${var.prefix}-web"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  sku                 = var.app_service_sku
  registry_url        = "https://${azurerm_container_registry.app.login_server}"
  image_name          = "launchpad:${var.image_tag}"
}
```

`source` locates reusable code; inputs are passed explicitly. The child declares
typed variables, creates resources, and publishes outputs. `module.web.url`
accesses an output. The resource address is
`module.web.azurerm_linux_web_app.app`, not just the Azure app name.
References create implicit dependencies. Child modules inherit the root's
provider configuration; `required_providers` identifies which provider they use.

In this repository:

- Root `infra/azure`: demo resource group, ACR, module calls and AcrPull assignments.
- Child `modules/web`: Linux service plan and App Service custom container.
- Child `modules/vm`: network, public IP, NSG, NIC, VM and cloud-init.
- Root outputs provide target names to pipeline configuration.

Modules are organizational/reuse boundaries, not automatic separate state
files. These two children share the Azure root's state. The Docker root and
import root use separate states.

## 3. Review the Azure architecture before creating anything

```text
tested source -> amd64 Docker image -> ACR digest
                                   |-> App Service (HTTPS)
                                   |-> Linux VM -> Docker localhost:8000
                                                    ^
                                     client -> Nginx HTTP:80
```

The same image runs on both targets. ACR admin credentials are disabled.
The registry uses **RBAC Registry Permissions** (`LegacyRegistryPermissions`),
matching the AcrPush/AcrPull roles; do not change to ABAC mode without updating
roles and guides. Each runtime has a system-assigned managed identity with
AcrPull on this registry. Pipelines need publishing and target-deployment roles.

The VM allows port 80 only; other ingress, including SSH, is denied. Azure VM
Run Command executes through its agent, not public SSH. A provisioner still
needs a public SSH key for VM creation; **do not publish its private half**.
Cloud-init installs Docker, Nginx and Azure CLI from Microsoft's signed repo.
Nginx proxies to `127.0.0.1:8000` and forwards the host/client/protocol headers.
The container is published only on VM localhost. This demo's public HTTP is
for non-sensitive teaching traffic; use a domain/TLS/private controls before
real workloads. Cloud-init is first-boot configuration, not a deployment pipeline.

Terraform owns infrastructure; pipelines own image releases. The web module
ignores only `docker_image_name` changes to prevent a later Terraform apply
from rolling back a pipeline release. Other infrastructure drift remains visible.
This ownership exception is intentional, not a generic `ignore_changes = all`.

## 4. Initiate the Azure root locally

Prerequisites: an approved subscription and cost budget; capacity/quota in your
chosen region; permission to create resources plus assign runtime roles
(Contributor alone cannot assign roles; Role Based Access Control Administrator
or a suitable approved equivalent is needed).

From the repository root:

```bash
az login
az account list --output table
export ARM_SUBSCRIPTION_ID="YOUR_APPROVED_SUBSCRIPTION_ID"
az account set --subscription "$ARM_SUBSCRIPTION_ID"
az account show --query '{name:name,id:id}' -o table
az provider register --namespace Microsoft.Web --wait
az provider register --namespace Microsoft.Compute --wait
az provider register --namespace Microsoft.Network --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.Storage --wait
ssh-keygen -t ed25519 -f "$HOME/.ssh/mmaug-demo" -C "mmaug-demo"
cd infra/azure
cp terraform.tfvars.example terraform.tfvars
# Edit YOUR subscription, unique prefix, region, and PUBLIC-key path.
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=azure.tfplan
```

The provider disables automatic resource-provider registration, so the explicit
registration commands above must be permitted and completed. This makes
permission requirements visible rather than silently registering namespaces.
Never apply the placeholder all-zero subscription. Confirm the plan's targets,
names, paid SKU, network exposure and role assignments. Do not claim an exact
monthly price; check your region, offers and subscription.

```bash
# Only after cost and plan approval:
terraform apply azure.tfplan
terraform output
```

No backend block is active initially, so this root begins with local state.
The initial image tag `bootstrap` may not exist yet: App Service can be provisioned
before the app is ready. Infrastructure apply is not a successful app deployment.
Build/push `bootstrap` or configure/run a pipeline as described in the Docker and
pipeline guides. Cloud-init and new RBAC assignments also require time to become
ready. A deployment checks health and fails visibly if prerequisites are not ready.

## 5. Bootstrap Azure Blob state storage separately

A backend must exist **before** Terraform initializes it. Do not create the
backend storage inside the same root whose state depends on that storage.
The supplied script uses interactive Azure CLI user login and Entra data-plane
auth, not account keys.

From the repository root, in a terminal with `az login` completed:

```bash
export ARM_SUBSCRIPTION_ID="YOUR_APPROVED_SUBSCRIPTION_ID"
export LOCATION="westeurope"
export STATE_RG="mmaug-state-rg"
export STATE_ACCOUNT="youruniquelowercasestate26"
bash scripts/bootstrap-state.sh
```

The script validates the account name, selects the subscription, reads the
signed-in user's object ID, asks for explicit `CREATE`, creates the RG/account,
disables anonymous blobs and shared-key auth, and assigns Storage Blob Data
Contributor to the instructor at this account. It does not create VM/app resources.
After RBAC propagation:

```bash
az storage container create --name tfstate --account-name "$STATE_ACCOUNT" \
  --auth-mode login --public-access off
```

If forbidden, confirm data-plane role and propagation; management-plane
Contributor is not Blob Data Contributor. Production backends should also
restrict network access appropriately and consider versioning/retention and
recovery requirements. This account uses Standard LRS for a teaching lab.

## 6. Migrate existing local state, without rebuilding resources

Stop every writer to this root and agree on a maintenance window. Keep the
same subscription, workspace, variables and resource configuration.

From `infra/azure`:

```bash
terraform workspace show
terraform state list
umask 077
mkdir -p state-backups
cp terraform.tfstate state-backups/pre-migration.tfstate
cp backend.tf.example backend.tf
cp backend.hcl.example backend.hcl
# Edit backend.hcl: actual account, tfstate container, unique key.
terraform init -migrate-state -backend-config=backend.hcl
# Read and answer the prompt to copy existing state to the backend.
terraform state list
terraform plan -out=after-migration.tfplan
```

`use_azuread_auth = true` selects Entra Blob authorization. The backend uses
the logged-in Azure CLI in this local-user flow when no competing service
principal, MSI, OIDC, access-key or SAS credentials are configured. No storage
key is included. The account,
container and blob key identify where state is stored. Backend configuration
cannot use ordinary `var.*` references because it initializes before normal
resource evaluation. This example deliberately omits `use_cli`, which is not
an accepted backend argument in Terraform 1.5.7; CLI authentication is implicit
in that version. `backend.tf` and `backend.hcl` are local generated files
ignored by Git. Commit the `.example` templates only.

After migration, check blob **metadata**, not state contents:

```bash
az storage blob list --account-name "$STATE_ACCOUNT" --container-name tfstate \
  --auth-mode login --query '[].name' -o table
```

The plan should show no infrastructure change caused merely by moving storage.
Investigate unrelated drift or pending input changes before applying anything.
Retain a protected backup until verified; never upload it publicly.

**Do not substitute `init -reconfigure` for migration.** Reconfigure accepts
new backend settings without copying the old state. It is suitable for an
already-populated backend during a later clone, not for moving the only local
state. Do not use `-force-copy` just to suppress a prompt.

## 7. State, locking, secrets and collaboration

- Remote Blob state centralizes the management record, not the `.tf` source.
- Azure Blob leases provide supported backend locking during writes.
- A lock prevents concurrent Terraform writes; it is not an approval gate.
- Marking an output `sensitive` hides display, not necessarily state contents.
- Do not print/download full state in a recorded public demo.
- Distinct roots/environments need distinct blob keys, and controlled workspaces.
- Unlock only after confirming the owner is no longer running:
  `terraform force-unlock LOCK_ID` is an emergency operation, not routine cleanup.
- A second collaborator initializes the same populated backend with
  `terraform init -backend-config=backend.hcl`; they do not migrate an empty
  local state over the existing record.
- CI identities use OIDC/workload identity federation rather than CLI-user
  sessions or storage keys. This sample's **application deployment** pipelines
  do not run Terraform, so they need no state-storage role. A future Terraform
  pipeline would configure backend OIDC and grant its own Blob data role.

## 8. Terraform import: adopt, do not recreate

Use the isolated `infra/import` root, not the already-managed demo resource group.
Import associates an existing Azure ID with the configured Terraform address.
It does not generate all HCL or change the live resource on its own.

From the repository root:

```bash
az group create --name mmaug-import-demo-rg --location westeurope
cd infra/import
export TF_VAR_subscription_id="$ARM_SUBSCRIPTION_ID"
terraform init
terraform validate
terraform import azurerm_resource_group.imported \
  "/subscriptions/$ARM_SUBSCRIPTION_ID/resourceGroups/mmaug-import-demo-rg"
terraform state list
terraform plan -out=import-review.tfplan
```

Never import a resource already owned by another Terraform state. Confirm
ownership and backups first. The HCL must match the imported object's location,
name, tags and other managed settings. If plan proposes changes, understand and
adjust configuration; **do not blindly apply** a destructive proposal.
`terraform state show ADDRESS` can help privately inspect attributes, but may
expose values and is not suitable for a public screen without review.

Terraform 1.5+ also supports configuration-driven import:

```hcl
import {
  to = azurerm_resource_group.imported
  id = "/subscriptions/YOUR_ID/resourceGroups/mmaug-import-demo-rg"
}
```

Place this in a temporary local `.tf` file instead of running CLI import, review
its plan, then apply the import plan. This is an **alternative**, not a second
import of the same address. Imported resources become managed; future destroy
can delete them. Importing is not an automatic safety shield.

## 9. Cleanup order and costs

The import RG must be an empty, dedicated teaching group before destroying it:

```bash
# In infra/import:
terraform plan -destroy -out=import-cleanup.tfplan
# Confirm only your empty teaching RG is affected.
terraform apply import-cleanup.tfplan
```

For Azure demo infrastructure:

```bash
# In infra/azure, using the working local or migrated backend:
terraform plan -destroy -out=azure-cleanup.tfplan
# Review the group and ALL contained resources before proceeding.
terraform apply azure-cleanup.tfplan
terraform state list
```

Do not delete backend storage first. After all states referencing it have been
retired and any recovery retention requirements are satisfied, the instructor
may delete the **dedicated** backend RG explicitly:

```bash
az group delete --name "$STATE_RG"
```

Read the confirmation. Do not use a shared resource group here. VM deallocation
does not remove disk/IP/storage costs; stopping the web app does not stop
App Service plan billing.

References:
[Terraform modules](https://developer.hashicorp.com/terraform/language/modules),
[azurerm backend](https://developer.hashicorp.com/terraform/language/backend/azurerm),
[import](https://developer.hashicorp.com/terraform/cli/commands/import),
[Azure state storage](https://learn.microsoft.com/azure/developer/terraform/store-state-in-azure-storage),
[Azure provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs).
