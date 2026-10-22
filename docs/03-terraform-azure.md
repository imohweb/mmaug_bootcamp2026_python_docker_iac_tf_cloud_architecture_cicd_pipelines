# 03 - Terraform, existing resources and OIDC remote state

Terraform state maps resource addresses to Azure objects. A saved plan previews
changes; apply executes those changes. Neither a valid configuration nor a
successful login proves authorization to provision resources or manage RBAC.

## Local foundations lab

The [Docker-provider root](../support-agent/terraform/main.tf) still manages the
single combined image, a localhost port and a named data volume. Build
`mmaug-support-agent:1.0`, supply `TF_VAR_specialist_token` and follow
[the Docker guide](02-docker.md). Its state can contain the sensitive token.
Review local destroy before removing its data volume.

## Azure ownership

The current Azure target is the existing **RG-MMAUG-Bootcamp**. Terraform must
read it as a data source, never create or delete it. The workload consists of:

- Shared Linux App Service plan and separate backend/frontend web apps.
- ACR with managed-identity pulls and two image repositories.
- Foundry account, project, model deployment and prompt agent.
- Azure AI Search with indexed Blob knowledge / Foundry IQ integration.
- Scoped managed-identity roles and knowledge/index configuration.

The storage account is bootstrapped outside the workload Terraform root and
has private `tfstate`, `knowledge` and `tickets` containers. State storage
cannot depend on resources created by the very state backend being initialized.
Applications have no access to `tfstate`; backend ticket write and source
knowledge read are isolated. No VM is deployed.

## Infrastructure pipeline

[infra.yml](../.github/workflows/infra.yml) uses GitHub OIDC and environment
**dev**, matching the existing SP federation. Read its dispatch inputs and
environment-variable names before running it. It executes storage bootstrap
before backend initialization, then validation/plan and an explicitly selected,
reviewed apply. Protect the environment with reviewers/branch restrictions;
these are external settings, not something Terraform's YAML guarantees.

The existing Contributor assignment is RG-scoped. An administrator must prepare
RBAC administration and Blob/Search/Foundry data access; bootstrap does not
grant itself new roles. Do not broaden to subscription Owner to bypass a
missing prerequisite. Resource providers must already be registered when the
SP cannot register them.

`provider.tf` declares providers and Azure AD storage authentication.
`dev.tfvars` is placeholder-only. Inject actual subscription, prefix and storage
values from protected CI configuration; never commit them.

For schema-only local checks:

```bash
cd infra/azure
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate
```

For a live plan, use the documented authenticated backend initialization and
values from the pipeline. Planning/applying the root requires backend Python
dependencies for the agent/index bridge. Execute only after authorization;
never run a speculative apply to discover what it will create.

## Existing-state migration: stop before a first pipeline apply

The checkout can contain ignored local state from the earlier teaching app.
Do not automatically initialize an empty remote backend and start creating
duplicate resources.

1. Identify the authoritative state and stop other writers.
2. Back it up privately. Do not print state in a workshop or CI log.
3. Review resource addresses affected by converting RG ownership to a data
   source, changing one web app into two and externalizing storage.
4. Explicitly remove shared-resource ownership from the old state only after
   review; never destroy a shared RG to resolve an address change.
5. Import or move retained workload resources where appropriate.
6. Use `terraform init -migrate-state` with the reviewed backend configuration,
   then verify a complete plan before apply.

Migration is not automatic. Old VM/network resources, the old agent or app may
be scheduled for deletion/replacement depending on the state. Review every
destructive action. Never execute an old saved plan against the rebuilt root.
Azure Blob lease locking coordinates writers; it is not an approval mechanism.

## Knowledge, runtime releases and cleanup

Knowledge Markdown lives in source control. Azure ingestion and the agent's
indexed retrieval must be verified, not merely source upload or HTTP liveness.
Read [Foundry](06-foundry-demo.md) for the current integration.

Application pipelines own image digests and the specialist-token setting;
Terraform ignores those release-owned fields so future applies do not revert
the selected images. Record outputs for both app names/URLs and ACR.

App Service, Search, ACR, Storage and model usage incur costs. A stopped app
does not stop plan billing. Review an authorized destroy plan and retain state
until workload resources are gone. Cleanup of bootstrapped storage is a separate
explicit action. Never delete RG-MMAUG-Bootcamp or its unrelated resources.

See [skills.md](../skills.md) for the standardized runbook and
[pipelines](04-pipelines.md) for release responsibilities.
