# Start here: one app, four execution environments

This public repository supports both the **17 October 2026** fundamentals
session and the **27 October 2026** session, **Advanced Cloud Architecture &
DevOps CI/CD Pipeline Process**. Both use the same application, infrastructure
examples and pipeline code. Presenter notes are intentionally not included.

For October 17, begin with local Python, Docker and Terraform. For October 27,
refresh those checks, then continue into the Azure modules, state workflow,
pipeline configuration and DevSecOps guides. A second application clone is not
required.

## 1. Clone and choose a directory

```bash
git clone https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_fundamentals_beginner_level.git
cd mmaug_bootcamp2026_python_docker_iac_fundamentals_beginner_level
git branch --show-current
# Expected: main
cd launchpad-lab
```

If using the supplied local folder, open a terminal inside `launchpad-lab`.
Paths in examples are relative to the cloned repository, not the presenter's
personal computer.

## 2. Local Python

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
python app.py
```

Expected test count: **11 methods**, with more input cases covered by subtests.
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

## 4. Follow the sequence

1. Prove Python behavior and validation.
2. Build and run Docker; stop/remove the named manual container.
3. Keep the image; let Terraform manage its own local container.
4. Azure extension: review paid infrastructure, then configure a pipeline.
5. Migrate that root's local state to Azure Blob without recreating resources.
6. Import a separate existing resource into the isolated import exercise.
7. Review DevSecOps controls; never interpret a green pipeline as proof of safety.

Each guide says **which directory and terminal** to use. Saved plans and state
are private operational data. The public PDF is a reading aid; copy executable
code from repository files.

## 5. Returning for October 27

Use your existing clone. Check local changes before updating from `main`; keep
your own work and do not overwrite it to match a demo.

Before the advanced session:

- Reconfirm the Python tests and Docker image build.
- Review [Azure architecture, modules and state](03-terraform-azure.md).
- Read [pipeline prerequisites and identity configuration](04-pipelines.md).
- Review [what CodeQL does and does not enforce](05-devsecops-codeql.md).
- Run `bash tests/test-deploy.sh` from the repository root for offline checks.
- For live Azure exercises, confirm the subscription, resource ownership,
  approvals, capacity and cost budget again.

Do not keep paid resources running merely to retain continuity between dates.
Source reuse and live-resource lifecycle are different responsibilities.
