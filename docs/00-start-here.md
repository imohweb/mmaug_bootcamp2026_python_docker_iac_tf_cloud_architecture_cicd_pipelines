# Start here: one support agent, four ways to run it

These teaching notes support the MMAUG bootcamp sessions on **17 October 2026**
and **27 October 2026 — Advanced Cloud Architecture & DevOps CI/CD Pipeline
Process**. The rebuilt application is a customer-support agent: a customer
submits a question in a React portal, the backend classifies it, searches the
knowledge source, drafts a response and assigns a specialist. A human reviews
and approves or reassigns the ticket; only an approved answer is shown to the
customer. See the [architecture diagram](./architecture.md).

The cloud edition now has **separate frontend and backend web apps** in the
existing RG-MMAUG-Bootcamp, with an OIDC infrastructure pipeline, external
storage bootstrap and indexed knowledge. The commands below remain the simple
offline lab. For the split-container rehearsal and cloud release procedures,
use [skills.md](../skills.md) and the [root README](../README.md).

The 17 October foundations still apply: Python, Docker and introductory
Terraform. On 27 October, use the same clone for Azure architecture, storage,
collaborative state, delivery pipelines, CodeQL and the optional Foundry demo.

## 1. Clone and choose the application folder

```bash
git clone https://github.com/imohweb/mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines.git
cd mmaug_bootcamp2026_python_docker_iac_tf_cloud_architecture_cicd_pipelines
git branch --show-current
# Expected: main
cd support-agent
```

If you already cloned the repository, keep your working folder and check your
uncommitted changes before updating. The application is in `support-agent/`;
Azure infrastructure, scripts, workflows and the docs are siblings at the
repository root. Commands below say which directory they expect.

## 2. Run and test the backend

From the repository root:

```bash
cd support-agent/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
export SPECIALIST_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python app.py
```

The local default uses `LocalStore` under `backend/.data`, seeds the four
Markdown knowledge documents, and runs with `AI_MODE=off`; no Azure account or
paid model is needed. Keep this terminal open. From another terminal, verify:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/config
curl -i -X POST http://127.0.0.1:8000/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alex","email":"alex@example.com","message":"I was charged twice for my subscription."}'
```

The creation response is HTTP 201 with a ticket and one-time customer access
key. The specialist console is at `http://127.0.0.1:8000/#/specialist`; enter
the generated specialist token. Stop the Flask development server with Ctrl+C.

## 3. Run the React portal

In another terminal, from the repository root:

```bash
cd support-agent/frontend
npm ci
npm test
npm run dev
```

Open the Vite URL printed in the terminal. Its development proxy sends `/api`
requests to `127.0.0.1:8000`, so the backend must still be running. Build the
production assets with `npm run build`; Flask can serve the built UI. The
customer portal saves ticket IDs and access keys in browser localStorage so it
can poll for the approved response. Treat that browser profile as private.

Backend tests are run with `python -m unittest` from `support-agent/backend`;
frontend tests with `npm test` from `support-agent/frontend`. From the repository
root, `bash tests/test-deploy.sh` runs offline mocked deployment-script checks.

## 4. October 17: foundations sequence

1. Trace a ticket from the customer form through triage, draft and human review.
2. Run the Python backend and React frontend; inspect the offline tests.
3. Build and run the Docker image, then compare Compose with the local Docker
   Terraform lab in the [Docker guide](02-docker.md).
4. Discuss modules, state and plans with the [Terraform guide](03-terraform-azure.md);
   do not provision paid Azure resources as a prerequisite for the foundations.
5. Preview the later session's architecture and delivery topics without
   configuring a release identity or enabling paid AI.

## 5. October 27: architecture, CI/CD and DevSecOps

Use your existing clone. Review local changes before updating; do not overwrite
your work to match a demonstration. Before the session, refresh the backend and
frontend tests, review [Azure storage and Terraform state](03-terraform-azure.md),
[pipeline setup](04-pipelines.md), [CodeQL scope](05-devsecops-codeql.md), and
[the optional AI demo](06-foundry-demo.md). Check the subscription, resource
ownership, model capacity and cost budget before any live exercise.

During the session:

1. Follow the customer-to-specialist-to-customer flow and the
   [architecture diagram](./architecture.md).
2. Review App Service, Blob Storage, container images, identity/RBAC and the
   change from the previous VM-based teaching example. Read the existing-state
   warning before planning infrastructure changes.
3. Trace GitHub Actions and Azure Pipelines, their test/build/deploy handoffs,
   workload identity and immutable image digest. Use one release orchestrator
   against shared targets at a time.
4. Review CodeQL results and distinguish a successful scan from an alerts-based
   merge or deployment gate.
5. For the optional Foundry exercise, compare offline templates, direct model
   calls and the prompt agent; all drafts still require human approval.
6. Verify deployment health, configuration and specialist access to Blob-backed
   knowledge, then clean up only resources owned by the lab.

Earlier October sessions used a different introductory app and VM examples;
those examples are not the current solution. The old application and VM
provisioning path have been removed. Historical session dates explain the
learning sequence, not a second deployment target.
