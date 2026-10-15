# Start here: one app, four execution environments

This public repository supports both the **17 October 2026** fundamentals
session and the **27 October 2026** session, **Advanced Cloud Architecture &
DevOps CI/CD Pipeline Process**. Both use the same application, infrastructure
examples and pipeline code.

For October 17, complete local Python, Docker and Terraform. Detailed pipeline
and DevSecOps exercises are reserved for October 27. On that date, refresh the
local checks and continue into Azure architecture, collaborative state, advanced
delivery and CodeQL. A second application clone is not required.

## 1. Clone and choose a directory

```bash
git clone https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines.git
cd mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines
git branch --show-current
# Expected: main
cd launchpad-lab
```

If using the supplied local folder, open a terminal inside `launchpad-lab`.
Paths in examples are relative to the cloned repository.

If you cloned before the repository was renamed, keep your existing folder.
From that clone's root, update its remote:

```bash
git remote set-url origin https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines.git
git remote -v
```

GitHub redirects old repository links, but the GitHub Actions OIDC subject
changes with the repository name. If Azure federation was already configured,
update its trust as explained in the [pipeline guide](04-pipelines.md).

## 2. Local Python

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
python app.py
```

Expected test count: **27 methods**: 11 foundation tests plus 16 offline AI
request-guard, mocked SDK and agent-lifecycle tests. Additional input cases use
subtests. No Azure credentials or model tokens are needed to run the tests.
The development server occupies this terminal; use a second terminal:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS "http://127.0.0.1:8000/sum?values=5,10,15"
curl -i "http://127.0.0.1:8000/sum?values=5,nope,15"
```

Expected success payloads, ignoring JSON whitespace and key order:

```json
{"status": "ok"}
{"total": 30, "average": 10.0}
```

The final request intentionally returns **HTTP 400** with an `error` field.
Open <http://127.0.0.1:8000/ui> in your browser. Stop the server with Ctrl+C.
For a production-style local server on macOS/Linux:

```bash
gunicorn --bind 127.0.0.1:8000 --workers 2 --access-logfile - app:app
```

Gunicorn is Unix-oriented; Windows users run `python app.py` for development,
then run the Linux container for the deployment-equivalent server.

## 3. Windows PowerShell equivalents

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest -v
python app.py
# Second terminal:
curl.exe -fsS http://127.0.0.1:8000/health
curl.exe -fsS "http://127.0.0.1:8000/sum?values=5,10,15"
```

If policy blocks activation, use `.\.venv\Scripts\python.exe` directly; do not
weaken an organization's execution policy for a lesson.

For local configuration:

```bash
APP_MESSAGE="Hello from Python!" python app.py
```

```powershell
$env:APP_MESSAGE = "Hello from Python!"
python app.py
```

Use the Bash commands on a Linux/WSL terminal for Azure shell scripts. They are
not PowerShell scripts. Do not copy Bash `\` line continuations into PowerShell.
Single-line Docker and Terraform examples work in either shell.

## 4. October 17: foundations sequence

1. Prove Python behavior and validation.
2. Build and run Docker; stop/remove the named manual container.
3. Keep the image; let Terraform manage its own local container.
4. Explain modules, state, plans and controlled changes using the
   [Terraform guide](03-terraform-azure.md).
5. Destroy only the local lab's managed resources, then remove its named image.
6. Close with a short overview of how tests and an image feed delivery on
   October 27. Do not configure cloud release identities or run a CodeQL
   workshop as part of this session.

Each guide says **which directory and terminal** to use. Saved plans and state
are private operational data. The public PDF is a reading aid; copy executable
code from repository files. Advanced CI/CD and DevSecOps slides in the existing
pack are optional October 27 reference, not October 17 lab requirements.

## 5. October 27: advanced architecture, CI/CD and DevSecOps sequence

Use your existing clone. Check local changes before updating from `main`; keep
your own work and do not overwrite it to match a demo.

Before the advanced session:

- Reconfirm the Python tests and Docker image build.
- Review [Azure architecture, modules and state](03-terraform-azure.md).
- Read [pipeline prerequisites and identity configuration](04-pipelines.md).
- Review [what CodeQL does and does not enforce](05-devsecops-codeql.md).
- For the optional AI demo, read [Foundry, Azure OpenAI and Docker-to-ACR](06-foundry-demo.md);
  review model availability, quota, costs and local configuration before enabling it.
- Run `bash tests/test-deploy.sh` from the repository root for offline checks.
- For live Azure exercises, confirm the subscription, resource ownership,
  approvals, capacity and cost budget again.

Do not keep paid resources running merely to retain continuity between dates.
Source reuse and live-resource lifecycle are different responsibilities.

During the session:

1. Compare App Service and VM/Nginx responsibilities; review the Terraform
   modules and paid-resource plan before provisioning.
2. Review Azure Blob state migration, locking and resource import. Keep one
   owner per state; do not import resources already owned by another root.
3. Configure protected environments, federated identities and pipeline
   variables using [the delivery guide](04-pipelines.md).
4. Trace GitHub Actions and Azure DevOps stages and the immutable image digest.
   Use only one orchestrator against the shared targets at a time.
5. Complete [the DevSecOps/CodeQL workshop](05-devsecops-codeql.md): inspect
   analysis jobs and alerts, review permissions, and distinguish existing
   checks from additional policy gates.
6. Review release evidence, approve a demo deployment, verify both targets,
   and discuss failure handling and known-good-digest rollback.
7. Identify missing production controls, then clean up resources in the
   documented order before retiring their state storage.

For the optional AI extension, compare direct model and deployed agent calls,
build/run locally with Docker Desktop, then push to ACR and verify the same
image in App Service using the [complete AI demo sequence](06-foundry-demo.md).
The VM is a non-AI hosting comparison target. Terraform creates it regardless
of whether Foundry is enabled.

CodeQL remains active in the repository regardless of the teaching date.
Moving its workshop to October 27 does not disable scans or automatically add
an alerts-based deployment gate.
