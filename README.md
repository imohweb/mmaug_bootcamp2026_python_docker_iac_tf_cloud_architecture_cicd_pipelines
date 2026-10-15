# MMAUG Bootcamp 2026: Python, Docker, Terraform, Cloud Architecture & CI/CD Pipelines

**27 October: Advanced Cloud Architecture & DevOps CI/CD Pipeline Process**,
building on the **17 October Python, Docker & Terraform fundamentals**.

Public repository:
[mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines](https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines).

One shared participant repository for two connected sessions:

| Date | Session | Learning path |
| --- | --- | --- |
| **17 October 2026** | **Python, Docker & Terraform IaC Fundamentals for Beginners** | Understand and test the app, package it, and learn the Terraform workflow. A short CI/CD handoff overview only; no DevSecOps workshop. |
| **27 October 2026** | **Advanced Cloud Architecture & DevOps CI/CD Pipeline Process** | Azure architecture, advanced GitHub Actions/Azure DevOps delivery, federated identities, approvals, verification, recovery and the DevSecOps/CodeQL workshop. |

The hands-on journey follows one Python web application from local execution
through Docker packaging to Terraform-managed resources and Azure delivery.
Both dates use this renamed repository and the same application; there is no
separate October 27 copy of the Python app.

## Choose your session

### 17 October: build the foundations

Start with [setup](docs/00-start-here.md), [Python](docs/01-python-explained.md)
and [Docker](docs/02-docker.md), then the local Docker Terraform exercise in
the [Terraform guide](docs/03-terraform-azure.md). Explain modules, state and
the purpose of automation without requiring pipeline or scanner configuration.

The checkpoint is a tested app running locally, in Docker and under Terraform
control, followed by scoped cleanup. A short "tests -> image -> deployment"
overview can bridge to the next session. Detailed pipeline configuration,
federation, release approvals and **all DevSecOps/CodeQL exercises belong to
27 October**, not the October 17 lab.

### 27 October: advanced CI/CD and DevSecOps workshop

Carry forward the tested `launchpad-lab` app and its container contract:

1. Compare App Service and VM/Nginx hosting responsibilities using the
   [Azure architecture and Terraform modules](docs/03-terraform-azure.md).
2. Examine state ownership, Azure Blob backend migration, locking and import.
3. Configure federated identities, review permissions and trace the same image
   digest through [GitHub Actions and Azure DevOps](docs/04-pipelines.md).
4. Run the [DevSecOps and CodeQL workshop](docs/05-devsecops-codeql.md):
   review both language jobs, triage alerts, distinguish checks from security
   gates, and define the evidence required for release approval.
5. Run the offline deployment regression scenarios, approve a reviewed release,
   verify both public targets, and discuss partial failures and deliberate
   rollback using a known-good digest.
6. Review missing production controls and cleanup/cost responsibilities.
7. Optionally demonstrate [Foundry agents and Azure OpenAI](docs/06-foundry-demo.md):
   provision the opt-in AI extension, compare both SDK calls, build locally with
   Docker Desktop, push to ACR and run the image in App Service using managed identity.

These are learning paths through the existing materials, not a claim that
additional production controls are already implemented. The current VM remains
an HTTP-only teaching target, and CodeQL is standalone scanning, not an
automatic alerts-based release gate.

## Reading routes

| Material | 17 October | 27 October |
| --- | --- | --- |
| [Setup and command reference](docs/00-start-here.md) | Start here; follow the foundations sequence | Refresh local checks; follow the advanced sequence |
| [Python: every source file explained](docs/01-python-explained.md) | Core lab | Prerequisite/reference |
| [Docker: recipe, runtime, commands and troubleshooting](docs/02-docker.md) | Core lab | Image/runtime prerequisite |
| [Terraform: modules, local state, Azure Blob migration and import](docs/03-terraform-azure.md) | Local workflow and IaC concepts | Azure architecture and collaborative state workflow |
| [GitHub Actions and Azure DevOps delivery](docs/04-pipelines.md) | Optional reference, not a configuration lab | Advanced delivery workshop |
| [DevSecOps and CodeQL setup](docs/05-devsecops-codeql.md) | Reserved for the next session | DevSecOps workshop |
| [Foundry agent, Azure OpenAI and local Docker-to-ACR demo](docs/06-foundry-demo.md) | Optional instructor reference | Paid opt-in AI application extension |
| [Participant slide PDF: October 17 and 27](docs/MMAUG_Python_docker_terraform_Fundamentals_Participant.pdf) | Foundations slides | Advanced delivery, cloud-init, CodeQL and optional AI walkthroughs |

The shared slide pack includes both sessions. Its detailed CI/CD and DevSecOps slides
are reference material for October 27, not requirements to cover on October 17.
The session split changes the teaching order, **not** workflow triggers:
repository CI and CodeQL scanning remain enabled before and between sessions.

Successful pushes to `main` now hand off from CI to CD in both pipeline
definitions. Configure the required environment approvals, federation and
variables **before enabling these releases**; pull requests stay test-only.
Use only one release orchestrator against the shared Azure targets.
See the [delivery setup and execution order](docs/04-pipelines.md).

## Repository map

```text
launchpad-lab/       Python web app, tests, Dockerfile, Compose, local Docker IaC
infra/azure/        Azure root module plus reusable web and vm child modules
infra/import/       Isolated resource-group import exercise
scripts/            Backend bootstrap and shared deployment scripts
.github/workflows/  CI-to-CD handoff, CodeQL and approval-gated Azure deployment
pipelines/          Azure DevOps Test -> Build -> approval -> Deploy
tests/              Offline deployment-script regression scenarios
docs/               Participant PDF and public technical walkthroughs
```

The API responds at `/`, `/health`, and `/sum?values=5,10,15`. Open `/ui` for
the interactive web page. The calculation remains the same locally, in Docker,
in App Service, and on the Nginx-backed Linux VM.

The container uses Flask and Gunicorn instead of exposing a teaching HTTP
server to Azure. Python's local `app.run` is for development only.
Optional `POST /ai/model` and `POST /ai/agent` routes require a private demo
bearer token and configured Azure access. The local-only `.env-local` has
placeholders; commit only `.env-local.example`. AI resources remain disabled
in Terraform until `enable_foundry = true`. The unchanged local routes and
offline tests do not need an Azure subscription.
The VM exposes **HTTP only** for a short non-sensitive demo; add a domain,
TLS and proper access controls before real use. No public SSH ingress is opened.

## Prerequisites

Python 3.10+, Docker with a running Linux-container daemon, Terraform 1.5+ and
below 2.0, Git, curl and (for Azure) Azure CLI. Bash/zsh commands are primary;
Windows instructions are in the setup guide. Azure exercises are instructor-led
extensions, not prerequisites for the local labs.

## What is safe to publish

Application code, tests, example configuration, provider lock files, workflows
and participant documentation belong here. Never commit `.env`, keys, tokens,
actual `terraform.tfvars`, backend state, plan files or provider downloads.
Keep `.env-local` local and commit only `.env-local.example`. Inspect `git status`
before committing. This repository deliberately has no cloud credentials.

## Validation and limitations

Python unit and real HTTP tests, Terraform validation, pipeline/static checks
and presentation validation are performed locally. A live Azure deployment
requires the subscription, roles, identities, named pipeline environments and
variables described in the guides. No Azure resources are provisioned merely
by cloning this repository or opening the slides.

Run offline deployment checks from the repository root:

```bash
bash tests/test-deploy.sh
```

These mocked checks verify deployment logic without calling real Azure,
Docker or public endpoints. They do not replace a live Azure rehearsal.

**Azure exercises incur costs.** Do not provision resources until you have read
the prerequisites, reviewed the plan and understood the cleanup instructions.
App Service B1, the VM, disk, public IP, ACR and state storage can all incur
costs. No exact cost is promised; check regional pricing, capacity and quotas.
Stopping the web app does not stop its plan's billing. Destroy demo resources
before deleting their remote state storage.
Reusing this repository on October 27 does **not** require leaving paid demo
resources running between sessions. Preserve source and approved configuration,
follow the cleanup order, and provision again only when needed.
