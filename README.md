# MMAUG Bootcamp 2026: Python, Docker, Terraform, Cloud Architecture & CI/CD Pipelines

**27 October: Advanced Cloud Architecture & DevOps CI/CD Pipeline Process**,
building on the **17 October Python, Docker & Terraform fundamentals**.

Public repository:
[mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines](https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines).

One shared participant repository for two connected sessions:

| Date | Session | Learning path |
| --- | --- | --- |
| **17 October 2026** | **Python, Docker & Terraform IaC Fundamentals for Beginners** | Understand and test the app, package it, and introduce infrastructure and delivery concepts. |
| **27 October 2026** | **Advanced Cloud Architecture & DevOps CI/CD Pipeline Process** | Reuse the app to examine Azure architecture, infrastructure ownership, state, federated delivery, release controls and DevSecOps. |

The hands-on journey follows one Python web application from local execution
through Docker packaging to Terraform-managed resources and Azure delivery.
Both dates use this renamed repository and the same application; there is no
separate October 27 copy of the Python app.

## Choose your session

### 17 October: build the foundations

Start with [setup](docs/00-start-here.md), [Python](docs/01-python-explained.md)
and [Docker](docs/02-docker.md), then the local Docker Terraform exercise in
the [Terraform guide](docs/03-terraform-azure.md). Azure delivery and CodeQL
can be introduced as instructor-led previews.

### 27 October: deepen the architecture and delivery process

Carry forward the tested `launchpad-lab` app and its container contract:

1. Compare App Service and VM/Nginx hosting responsibilities using the
   [Azure architecture and Terraform modules](docs/03-terraform-azure.md).
2. Examine state ownership, Azure Blob backend migration, locking and import.
3. Configure federated identities, review permissions and trace the same image
   digest through [GitHub Actions and Azure DevOps](docs/04-pipelines.md).
4. Verify both deployments, discuss approvals and deliberate rollback, and
   inspect [CodeQL results and security-policy boundaries](docs/05-devsecops-codeql.md).
5. Run the offline deployment regression scenarios, then review cleanup and costs.

These are learning paths through the existing materials, not a claim that
additional production controls are already implemented. The current VM remains
an HTTP-only teaching target, and CodeQL is standalone scanning, not an
automatic alerts-based release gate.

## Start here

1. [Setup and command reference](docs/00-start-here.md)
2. [Python: every source file explained](docs/01-python-explained.md)
3. [Docker: recipe, runtime, commands and troubleshooting](docs/02-docker.md)
4. [Terraform: modules, local state, Azure Blob migration and import](docs/03-terraform-azure.md)
5. [GitHub Actions and Azure DevOps delivery](docs/04-pipelines.md)
6. [DevSecOps and CodeQL setup](docs/05-devsecops-codeql.md)
7. [17 October participant slide PDF](docs/MMAUG_Python_docker_terraform_Fundamentals_Participant.pdf)

## Repository map

```text
launchpad-lab/       Python web app, tests, Dockerfile, Compose, local Docker IaC
infra/azure/        Azure root module plus reusable web and vm child modules
infra/import/       Isolated resource-group import exercise
scripts/            Backend bootstrap and shared deployment scripts
.github/workflows/  CI, CodeQL and manually approved GitHub Azure deployment
pipelines/          Azure DevOps example
tests/              Offline deployment-script regression scenarios
docs/               Participant PDF and public technical walkthroughs
```

The API responds at `/`, `/health`, and `/sum?values=5,10,15`. Open `/ui` for
the interactive web page. The calculation remains the same locally, in Docker,
in App Service, and on the Nginx-backed Linux VM.

The container uses Flask and Gunicorn instead of exposing a teaching HTTP
server to Azure. Python's local `app.run` is for development only.
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
actual `terraform.tfvars`, backend state, plan files, provider downloads,
presenter PowerPoint files or speaker scripts. Inspect `git status` before
committing. This repository deliberately has no cloud credentials.

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
