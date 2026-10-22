# Python: the support-agent backend, module by module

The Flask service in `support-agent/backend/` handles the ticket API, agent
workflow, persistence and optional AI integrations. The React frontend lives
in `support-agent/frontend/`; Flask serves its production build. For the
end-to-end flow, see the [architecture diagram](./architecture.md).

## Python building blocks

```python
count = 5
text = "5"
print(type(count).__name__)  # int
print(text * 2)              # 55 as text
print(int(text) * 2)         # 10 as a number

values = [5, 10, 15]
summary = {"total": sum(values), "average": sum(values) / len(values)}
print(summary)
```

Names reference values. Lists preserve order, dictionaries map keys to values,
and type hints document intended inputs and outputs; they do not replace
runtime validation. `for` traverses a sequence, indentation defines blocks,
and `with` closes a resource reliably. Read the
[Python tutorial](https://docs.python.org/3/tutorial/) for more foundations.

## Application factory and HTTP routes — `app.py`

`create_app(store=None)` creates the Flask app and sets request-size and
container configuration. It accepts an injected store for tests. On first use,
its nested `services()` builds a store, knowledge base and ticket service;
`LocalStore` automatically receives knowledge seed files in offline mode.
The module-level `app = create_app()` is the WSGI object Gunicorn imports.
`main()` is only the local development entry point, on `127.0.0.1` and `PORT`
(default 8000).

Routes and contracts:

- `GET /health` returns `{"status":"ok"}`. It tests the process response, not
  every dependency.
- `GET /api/config` reports the configured AI mode and the four support teams.
- `POST /api/tickets` validates name, email and a 10–2,000 character message,
  then returns HTTP 201 with `{ticket, access_key}`.
- `GET /api/tickets/<id>` requires `X-Ticket-Key`. Invalid IDs/keys return the
  same not-found result.
- Specialist routes use `Authorization: Bearer <token>`: list/filter tickets,
  fetch a ticket, approve an edited or unchanged response, reassign to another
  category, and list knowledge documents. The console is disabled with HTTP
  503 unless `SPECIALIST_API_TOKEN` is configured; invalid tokens get 401.
- Invalid input returns 400, oversized request bodies return 413, and stale or
  invalid ticket-state updates return 409.

The specialist token must be at least 32 characters and must not be a
placeholder. The frontend keeps it in memory for the console session. The API
uses security headers and `Cache-Control: no-store` on API responses.

## Ticket lifecycle — `tickets.py`

`TicketService.create()` validates customer data, requests a draft from the
support agent, creates a `SUP-…` ticket ID and a random access key, and stores
only the key's SHA-256 hash with the ticket. Customer access compares hashes
using `secrets.compare_digest`; the customer view never exposes internal ticket
fields. The ticket initially has status `awaiting_approval`.

`approve()` accepts the specialist's final response (1–4,000 characters), marks
the ticket `responded`, records who approved it and appends history. `reassign()`
changes the specialist/category while approval is pending. Each update uses the
stored ETag; concurrent changes produce a conflict rather than silently
replacing newer data. Specialist assignment is billing → Aye Chan, technical →
Min Thu, account → Su Mon, general → Kyaw Zin.

## Storage abstraction — `storage.py`

The `Store` protocol defines list/read/write operations. `LocalStore` mirrors a
container/blob interface in `DATA_DIR` (default `backend/.data`) for local runs
and tests; it is intentionally single-process. `BlobStore` uses Azure Blob
Storage with `DefaultAzureCredential` when `STORAGE_ACCOUNT_URL` is set, or a
connection string when explicitly configured. Writes support create-only and
ETag conditional updates. Azure is the deployed system of record; the app does
not need a database for this lab.

## Knowledge search — `knowledge.py`

Knowledge documents are Markdown files with front matter and `##` sections.
The loader parses documents, tokenizes text, ranks sections by query-word
matches (with a small category bonus), and caches the loaded sections briefly.
Local mode copies the four files from `support-agent/knowledge`; Azure mode
reads the Markdown blobs uploaded into the private `knowledge` container.
The ranking is a small transparent teaching example, not vector search.

## Agent triage and drafting — `support_agent.py`, `ai_client.py`

`classify()` maps message keywords to billing, technical, account or general,
and marks urgent phrases high priority. `SupportAgent.draft()` searches
knowledge and creates a source-grounded draft. With AI disabled it uses a
knowledge-template response. When enabled, it submits a JSON-only prompt and
accepts only a bounded, valid reply/category/priority; any unavailable service,
malformed response or other AI error falls back to the template. A human
specialist still approves every response.

`ai_client.py` implements `AI_MODE=off|model|agent`: no AI call, Azure OpenAI
chat completion, or Foundry prompt-agent Responses call. It uses Azure identity
by default and optional OpenAI key auth only where configured. See
[the Foundry guide](06-foundry-demo.md) for setup, costs and the Terraform
agent bridge in `manage_agent.py`.

## Tests and React frontend

`test_app.py` covers API contracts, errors, auth and ticket lifecycle;
`test_agent.py` covers classification, search and fallback; `test_ai.py` uses
mocks for model/agent SDK behavior. Run them offline:

```bash
cd support-agent/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
```

The React 19 app uses `App.jsx` for config/navigation, `CustomerPortal.jsx` for
submitting and tracking tickets, `SpecialistConsole.jsx` for the authenticated
queue/review workflow, and `api.js` for fetch/error handling. Customer access
keys are stored in browser localStorage; specialist tokens are kept in memory.
`App.test.jsx` uses Vitest and mocks HTTP interactions. From
`support-agent/frontend`, run `npm ci`, `npm test`, and `npm run build`.

## What the example does not claim

The public ticket endpoint has no rate limiting; LocalStore is not safe as a
multi-process Azure store; specialists share one token; and there is no email
delivery. These are explicit extension points, not production-ready identity or
abuse controls.

References: [Flask application factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/),
[Python unittest](https://docs.python.org/3/library/unittest.html),
[React documentation](https://react.dev/learn).
