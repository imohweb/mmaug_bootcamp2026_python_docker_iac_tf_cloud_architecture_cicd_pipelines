# 06 — Foundry support-drafting agent

The optional Microsoft Foundry integration drafts responses for the customer
support workflow. It does not send replies autonomously: every draft is
reviewed and approved by a human specialist. The offline path is useful for
teaching and remains the default for local development. See the
[architecture diagram](./architecture.md).

## Cloud grounding: Foundry IQ, not only keyword excerpts

The cloud agent integration now provisions an Azure AI Search service and uses
the Foundry IQ agentic-retrieval chain:

```text
Blob knowledge container
  -> Blob data source / indexer
  -> semantic search index
  -> knowledge source + knowledge base
  -> managed-identity MCP connection
  -> Foundry agent retrieval tool
```

The setup bridge is `support-agent/backend/setup_knowledge_index.py`.
Infrastructure exposes `knowledge_setup_environment`; setup creates the
index/retrieval resources and verifies indexer completion before the agent is
registered. Use the infrastructure workflow rather than manually guessing
preview REST payloads. An indexer start response alone is not success.

The setup output supplies `FOUNDRY_SEARCH_ENDPOINT`,
`FOUNDRY_SEARCH_INDEX_NAME`, `FOUNDRY_KNOWLEDGE_SOURCE_NAME`,
`FOUNDRY_KNOWLEDGE_BASE_NAME`, `FOUNDRY_SEARCH_CONNECTION_NAME`,
`FOUNDRY_PROJECT_RESOURCE_ID`, `AZURE_STORAGE_RESOURCE_ID`,
`KNOWLEDGE_CONTAINER`, `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_DEPLOYMENT` and `AZURE_OPENAI_MODEL_NAME`.
The workflow passes these to:

```bash
python support-agent/backend/setup_knowledge_index.py
```

Official schemas: [search-index knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index),
[knowledge base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base),
[retrieve API](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
and [Foundry IQ managed MCP connection](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect).
The implementation selects Search/IQ API `2026-08-01-preview` and connection
ARM API `2025-10-01-preview`.

This integration uses preview APIs; **live Azure deployment is not yet
verified**. Check regional support and current service API compatibility before
authorizing apply. This is distinct from the classic Azure AI Search tool:
there is a knowledge base and an MCP retrieval connection, not just an index
name or app-side keyword retrieval relabeled as IQ.

Offline/model paths still use the source excerpts and template fallback.
AI_MODE=agent cloud grounding must be checked separately from that fallback:
submit a query that requires the indexed knowledge and inspect actual
retrieval evidence. Passing mocked SDK tests cannot prove a live retrieval.

## Three AI modes

| `AI_MODE` | Drafting behavior | External AI cost |
| --- | --- | --- |
| `off` | Searches the local/Blob knowledge source and creates a deterministic template. | None |
| `model` | Calls the configured Azure OpenAI deployment directly. | Model usage applies |
| `agent` | Calls the Foundry prompt agent `mmaug-support-agent`. | Model/agent usage applies |

The agent classifies a request as billing, technical, account or general,
sets priority high/normal, searches Markdown knowledge and grounds its draft in
matching excerpts. The specialist roster is billing → Aye Chan, technical →
Min Thu, account → Su Mon, general → Kyaw Zin. Draft metadata records its
source and knowledge documents. If AI is off, unavailable, throws an error, or
returns invalid JSON, the backend falls back to a knowledge-template draft.
This fallback does not bypass human approval.

## Prompt and response contract

The app sends a system instruction plus the customer message and retrieved
knowledge excerpts. The prompt asks for JSON only with this shape:

```json
{
  "category": "billing|technical|account|general",
  "priority": "normal|high",
  "reply": "A short draft grounded in the supplied excerpts"
}
```

The backend validates the reply text and allowed categories/priorities before
using any model-provided values. Instructions prohibit promises of refunds and
requests for passwords, full card numbers or API keys; if the knowledge does
not answer the question, the response should say a specialist will follow up.
Treat prompts and outputs as untrusted content: the specialist console lets a
human edit or reassign, and the customer receives nothing until approval.

## Local offline walkthrough

From the repository root, install backend dependencies and run both suites:

```bash
cd support-agent/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
```

With no storage endpoint, the app stores JSON tickets under `backend/.data`,
seeds knowledge from `support-agent/knowledge`, and defaults to `AI_MODE=off`.
The four Markdown files are general information, billing/payments, account and
security, and technical troubleshooting. You can use both the customer portal
and specialist console without Azure credentials; drafts use the template.

`test_agent.py` checks categorization, knowledge search and template fallback.
`test_ai.py` mocks model/agent SDK calls and exercises request/response handling;
it does not call Azure or incur model charges. Frontend `App.test.jsx` uses
mocked API responses. Run `npm test` and `npm run build` from
`support-agent/frontend`.

## Optional Terraform/Foundry configuration

`infra/azure/dev.tfvars` shows placeholders and current options: `enable_foundry`
(default true), `ai_mode` (`agent` or `model` when enabled), deployment name,
model/version/SKU/capacity, region and agent name. With `enable_foundry = false`,
Terraform sets the deployed app to `AI_MODE=off`; knowledge-template drafting
continues. The default model example is gpt-4.1-mini with a GlobalStandard
deployment, but model availability, regional support, capacity, quota and price
must be checked for the target subscription before planning any paid resources.
The default Foundry region may differ from the App Service region; verify data
residency requirements before choosing a global model SKU.

When enabled, `foundry.tf` creates the AI Services account, project and model
deployment; assigns scoped runtime roles; then uses
`support-agent/backend/manage_agent.py` as a Terraform data-plane bridge to
create the prompt agent. The default agent name is `mmaug-support-agent`. The
bridge requires the backend Python dependencies and Entra authentication during
Terraform apply and destroy. Prepare the interpreter before planning:

```bash
# From the repository root:
cd support-agent/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd ../..
export TF_VAR_agent_python_executable="$PWD/support-agent/backend/.venv/bin/python"
cd infra/azure
terraform plan -var-file=dev.tfvars -out=azure.tfplan
```

Review billable resources, role assignments and the whole plan; only apply
through the approved teaching workflow. Agent creation is not an ordinary
AzureRM resource operation: keep the bridge script and selected Python
environment available for destroy. If creation fails, inspect Azure and state
before retrying; do not discard state as a repair. Existing state from the
previous lab can replace the earlier dedicated agent while keeping the Foundry
project name for in-place updates. See the [Terraform guide](03-terraform-azure.md)
for the existing-state VM removal warning and cleanup workflow.

## App configuration and access

The backend reads `AI_MODE`, `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`,
`FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_AGENT_NAME`. `storage.py` selects Blob
Storage when `STORAGE_ACCOUNT_URL` is present. In local development,
`DefaultAzureCredential` can use the developer's existing Entra sign-in; in
Azure, App Service uses its managed identity. The Terraform example disables
storage shared keys and local Foundry key authentication. Do not copy secrets
into source, image layers, or committed variable files.

The console's shared `SPECIALIST_API_TOKEN` is separate from model credentials
and is configured by the deploy script. It is not user-specific identity.
Never place a live token in screenshots or logs.

## Costs and boundaries

AI calls may incur model usage and be constrained by regional quota. The public
ticket endpoint currently has no rate limiting, so abuse can generate paid
requests. For a live exercise, use a limited budget, a small capacity and a
short run window; prefer `off` for free offline tests. A human review step is
mandatory in this design, but it is not a substitute for monitoring, identity,
privacy controls or cost limits.

References: [Microsoft Foundry agents](https://learn.microsoft.com/azure/foundry/agents/overview),
[Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/overview),
[DefaultAzureCredential](https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains).
