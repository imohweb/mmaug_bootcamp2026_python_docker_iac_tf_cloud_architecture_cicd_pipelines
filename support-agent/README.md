# MMAUG Customer Support Agent (27 October 2026)

Customers submit queries, the agent triages them and drafts a reply from the
knowledge base, a human specialist approves it, and the response is delivered
back to the customer. See the [architecture](../docs/architecture.md).

```text
backend/     Flask API (app.py), tickets.py, support_agent.py, knowledge.py,
             storage.py (Blob or local folder), ai_client.py, seed_knowledge.py,
             manage_agent.py (Terraform Foundry agent bridge) and unit tests
frontend/    React + Vite: customer portal (#/) and specialist console (#/specialist)
knowledge/   Markdown knowledge source (uploaded to Blob Storage by Terraform)
terraform/   Local Docker-provider Terraform lab
Dockerfile   Multi-stage: Node builds React, Python 3.12 + Gunicorn serves API + UI
compose.yaml Local container on http://127.0.0.1:8090 with a data volume
```

Requirements: Python 3.10+, Node.js 22+, Docker (running), Terraform 1.5–1.x, curl.

## 1. Backend (Python)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest -v
export SPECIALIST_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
.venv/bin/python app.py          # http://127.0.0.1:8000
```

Optional: copy `.env-local.example` to `.env-local` for local settings (never commit it).
Without `STORAGE_ACCOUNT_URL` the app stores tickets in `backend/.data/` and
seeds the knowledge container from `../knowledge`.

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/config
curl -fsS -X POST http://127.0.0.1:8000/api/tickets -H 'Content-Type: application/json' \
  -d '{"name":"Thandar","email":"thandar@example.com","message":"I was charged twice for my invoice"}'
curl -fsS -H "Authorization: Bearer $SPECIALIST_API_TOKEN" \
  "http://127.0.0.1:8000/api/specialist/tickets?status=awaiting_approval"
```

| Method and path | Who | Purpose |
| --- | --- | --- |
| `GET /health` | anyone | Liveness |
| `GET /api/config` | anyone | AI mode and specialist teams |
| `POST /api/tickets` | customer | Create a ticket; returns `ticket` and a one-time `access_key` |
| `GET /api/tickets/<id>` + `X-Ticket-Key` | customer | Status and approved response |
| `GET /api/specialist/tickets?status=&category=` | specialist | Queue |
| `GET /api/specialist/tickets/<id>` | specialist | Ticket, draft, knowledge sources, history |
| `POST /api/specialist/tickets/<id>/approve` `{"response": "..."}` | specialist | Approve (optionally edited) and deliver |
| `POST /api/specialist/tickets/<id>/reassign` `{"category": "..."}` | specialist | Route to another team |
| `GET /api/specialist/knowledge` | specialist | Documents loaded from the knowledge container |

Specialist calls use `Authorization: Bearer $SPECIALIST_API_TOKEN` (32+ characters).

## 2. Frontend (React)

```bash
cd frontend
npm ci
npm test
npm run dev      # http://127.0.0.1:5173, proxies /api to the backend on :8000
npm run build    # dist/ is served by Flask at http://127.0.0.1:8000
```

## 3. Knowledge source

Each file in `knowledge/` has front matter (`title`, `category`) and `##`
sections. The agent searches the sections, cites the matches in the draft and
the specialist sees which sections were used. In Azure, `terraform apply`
uploads the files to the `knowledge` container; locally, seed or refresh with:

```bash
cd backend && .venv/bin/python seed_knowledge.py --overwrite
```

## 4. Docker

```bash
docker build -t mmaug-support-agent:1.0 .
export SPECIALIST_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build        # http://127.0.0.1:8090
docker compose down              # add -v to delete the ticket volume
```

## 5. Terraform (local Docker provider)

```bash
docker build -t mmaug-support-agent:1.0 .
cd terraform
export TF_VAR_specialist_token="$SPECIALIST_API_TOKEN"
terraform init
terraform plan -out=tfplan
terraform apply tfplan           # http://127.0.0.1:8080
terraform destroy
```

The sensitive token is stored in the local state file; keep state out of Git.

## 6. Azure

Azure infrastructure is in [`../infra/azure`](../infra/azure) and documented in
[Terraform and Azure](../docs/03-terraform-azure.md); AI drafting in
[Foundry](../docs/06-foundry-demo.md). This is a teaching app: one shared
specialist token, no rate limiting and portal-only delivery.

The cloud topology uses **two web apps** in existing RG-MMAUG-Bootcamp.
Build Docker targets `backend` and `frontend` separately; the frontend's Node
server proxies API/health to `BACKEND_ORIGIN`. For the equivalent local topology:

```bash
docker compose -f compose.split.yaml up --build -d
docker compose -f compose.split.yaml down
```

Export the specialist token first. Bootstrap creates the state, knowledge and
tickets containers before Terraform initialization. Source knowledge is indexed
through Azure AI Search / Foundry IQ for agent retrieval. GitHub infrastructure
and application workflows use the existing `dev` OIDC trust; see the
[reusable instructions](../skills.md) and [root README](../README.md).
