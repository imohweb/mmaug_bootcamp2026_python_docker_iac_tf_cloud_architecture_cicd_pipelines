# Expanded architecture views

These diagrams expand the compact architecture in the repository README and
separate four concerns so they are easier to read when presented individually.
They describe the **architecture encoded in the repository**, not proof that
the Azure resources have been deployed.

## 1. Runtime: customer, human review and grounded drafting

```mermaid
flowchart TB
    customer["Customer browser"]
    specialist["Specialist browser"]

    subgraph app["Two Azure App Service web apps"]
        frontend["Frontend<br/>React + Node static server"]
        backend["Backend<br/>Flask + Gunicorn"]
    end

    subgraph blobs["Private Blob containers"]
        tickets[("tickets<br/>ticket JSON + ETags")]
        knowledge[("knowledge<br/>Markdown policy source")]
    end

    subgraph retrieval["Azure AI Search / Foundry IQ"]
        indexer["Blob indexer"]
        index["Semantic search index"]
        source["Knowledge source"]
        kb["Knowledge base"]
        indexer --> index --> source --> kb
    end

    subgraph foundry["Microsoft Foundry project"]
        agent["Prompt agent<br/>mmaug-support-agent"]
        model["GPT-6.1-sol deployment<br/>alias: demo-model"]
        agent -->|"draft / classify"| model
        agent -->|"MCP tool: knowledge_base_retrieve"| kb
        kb -->|"retrieval reasoning uses configured deployment"| model
    end

    customer -->|"HTTPS: submit / track with ticket key"| frontend
    specialist -->|"HTTPS: queue / edit / approve / reassign"| frontend
    frontend -->|"same-origin API proxy over HTTPS"| backend
    backend -->|"managed identity: create / update / read"| tickets
    backend -->|"managed identity: read policy source"| knowledge
    knowledge -->|"managed identity: index Markdown"| indexer
    backend -->|"invoke existing agent"| agent
    backend -->|"validated draft stays pending"| tickets
    specialist -->|"approval is required"| backend
    backend -->|"approved response only"| frontend
    frontend -->|"customer polls with ticket key"| customer
```

[Open the runtime diagram full-size (SVG)](architecture/runtime-flow.svg)

**Important boundary:** the agent drafts and retrieves policy. The backend
validates the draft, and only a specialist can approve customer delivery.
Portal tracking is implemented; email/SMS delivery is not.

**Deployment alias:** `demo-model` is the Azure deployment name. The catalog
model configured behind it is `gpt-6.1-sol`, version `2026-09-29`. The agent
calls the deployment via the Foundry project; the backend also supports an
optional direct model mode.

## 2. Azure resources and ownership boundaries

```mermaid
flowchart TB
    browser["Public customer / specialist browser"]
    identity["Existing GitHub federated service principal<br/>OIDC subject targets environment dev"]
    admin["Administrator prerequisites<br/>RBAC management + Blob data permissions"]

    subgraph rg["Existing resource group: RG-MMAUG-Bootcamp<br/>Terraform reads this group; it does not own it"]
        subgraph plan["One Linux App Service plan"]
            webfront["Frontend Linux Web App<br/>React + Node proxy"]
            webback["Backend Linux Web App<br/>Flask + Gunicorn"]
        end
        acr["Azure Container Registry<br/>backend and frontend repositories"]
        subgraph storage["Bootstrapped Storage account<br/>created/reused before Terraform init"]
            state[("tfstate<br/>Terraform state + Blob lease")]
            kbdata[("knowledge<br/>Markdown source documents")]
            ticketdata[("tickets<br/>customer support records")]
        end
        search["Azure AI Search<br/>index + knowledge source/base"]
        subgraph foundry["Foundry account and project"]
            model["GPT-6.1-sol<br/>demo-model deployment"]
            agent["Prompt agent<br/>mmaug-support-agent"]
        end
    end

    browser -->|"HTTPS"| webfront
    webfront -->|"HTTPS proxy"| webback
    acr -->|"AcrPull: app managed identities"| webfront
    acr -->|"AcrPull: app managed identities"| webback
    webback -->|"Blob data roles, container-scoped"| ticketdata
    webback -->|"Blob read role, container-scoped"| kbdata
    kbdata -->|"Search identity reads source"| search
    webback -->|"Foundry runtime access"| agent
    agent -->|"model deployment"| model
    agent -->|"Foundry IQ MCP retrieval"| search

    admin -->|"provisions required scopes out of band"| identity
    identity -->|"bootstrap storage before init"| storage
    identity -->|"Terraform workload management"| rg
    identity -->|"Terraform Azure backend"| state
```

[Open the Azure resource diagram full-size (SVG)](architecture/azure-resources.svg)

The existing resource group, bootstrap-owned storage account/containers and
Terraform-managed workload have different lifecycle owners. The web apps are
PaaS resources; the diagram does not place them inside a VNet subnet. The
`tfstate` container is not an application data store or a Search source.

## 3. CI, CodeQL, application release and infrastructure delivery

```mermaid
flowchart TB
    repo["GitHub repository"]

    subgraph checks["Automatic checks: push / PR / manual CI"]
        ci["CI workflow<br/>unit tests, frontend build,<br/>container smoke, Terraform validate"]
        codeql["CodeQL workflow<br/>push / PR / weekly schedule<br/>Python + JS/TS + Actions"]
    end

    subgraph apprelease["Separate application release: manual dispatch on main"]
        release["Release checks"]
        build["Build two Docker targets"]
        push["Push both images and resolve SHA digests"]
        deploy["Deploy the two digests"]
        release --> build --> push --> deploy
    end

    subgraph infrastructure["Separate infrastructure workflow: manual dispatch on main"]
        bootstrap["Bootstrap private storage"]
        planstep["Terraform init / validate / plan"]
        review{"Explicit apply input<br/>+ configured dev reviewer"}
        apply["Apply exact saved plan"]
        resources["Creates/updates App Service,<br/>ACR, Foundry, Search and roles"]
        bootstrap --> planstep --> review --> apply --> resources
    end

    subgraph azure["Azure targets"]
        acr["ACR"]
        frontend["Frontend Web App"]
        backend["Backend Web App"]
        tfstate[("Blob: tfstate")]
    end

    repo --> ci
    repo --> codeql
    repo --> apprelease
    repo --> infrastructure
    push -->|"support-agent-frontend + backend digests"| acr
    deploy --> frontend
    deploy --> backend
    bootstrap -->|"create/reuse before init"| tfstate
    planstep -->|"OIDC + Entra backend"| tfstate
    apply -->|"same-run saved plan"| tfstate
    resources -->|"infrastructure outputs consumed by release"| deploy
```

[Open the CI/CD diagram full-size (SVG)](architecture/ci-cd.svg)

**GitHub CI does not deploy.** CodeQL is a separate scanning workflow. The
manual app-release workflow builds/pushes images and updates the App Services.
The manual infrastructure workflow bootstraps state storage, plans and applies
only when explicitly requested and the `dev` environment has its required
review protection. Storage bootstrap may create resources even when Terraform
apply is not selected.

**Azure DevOps is a separate alternative application-release pipeline**, not
the GitHub infrastructure workflow. Its current YAML has `main` triggers and
deployment enabled by default; do not let both release orchestrators target the
same apps at the same time.

## 4. Advanced architecture extensions (not in this deployment)

The following services in an expanded reference diagram are useful topics, but
they are **not currently declared by this repository's Terraform**:

| Extension | Appropriate role | Important diagram correction |
|---|---|---|
| Application Gateway WAF_v2 | Optional internet-facing edge, TLS termination/routing, WAF policy | Show Internet → Gateway/WAF → App Service. Port 80 should redirect to HTTPS rather than appear as the app's normal serving path. |
| VNet, private endpoints, private DNS | Private inbound app access and private service connectivity | App Service remains PaaS outside the subnet. A private endpoint is a NIC in a subnet. Gateway, private endpoint and App Service outbound integration have distinct subnet requirements. |
| Key Vault | Central secret/certificate lifecycle, accessed with managed identity | The current pipeline sets the specialist token as an App Service setting; no Key Vault resource/reference is in the current Terraform. |
| PostgreSQL | Relational ticket storage, if the data model needs transactions/queries | Current ticket persistence is JSON blobs with ETag conditional updates. PostgreSQL is not a second current ticket store. |
| Application Insights / Log Analytics / Azure Monitor | Instrumentation, log aggregation, dashboards and alerts | These are observability paths, not request-path services. They are not currently provisioned/instrumented in this codebase. |
| Embedding model and vector index | Vector/hybrid retrieval if implemented and evaluated | Current Search setup creates a semantic text index; no embedding deployment/vector field is configured. |

```mermaid
flowchart TB
    browser["Internet clients"]
    gateway["Optional Application Gateway WAF_v2<br/>separate gateway subnet"]
    privateEP["Optional App Service private endpoint NIC<br/>private-endpoint subnet"]
    app["App Service PaaS<br/>not hosted inside the subnet"]
    integration["Optional App Service VNet integration<br/>separate integration subnet"]
    services["Optional private service endpoints<br/>Storage / Search / Key Vault"]
    dns["Private DNS zones"]
    kv["Optional Key Vault"]
    pg["Optional PostgreSQL<br/>(replaces Blob ticket store only if redesigned)"]
    monitor["Optional App Insights + Log Analytics<br/>Azure Monitor alerts"]
    embed["Optional embedding deployment<br/>and vector fields"]

    browser --> gateway -->|"HTTPS; host/DNS/probes configured"| privateEP --> app
    app --> integration --> services
    privateEP -.-> dns
    integration -.-> dns
    app -. "managed identity" .-> kv
    app -. "future persistence choice" .-> pg
    app -. "instrumentation / telemetry" .-> monitor
    embed -. "future vector retrieval design" .-> services
```

[Open the optional extensions diagram full-size (SVG)](architecture/optional-extensions.svg)

Do not treat this extension diagram as an instruction to add every service.
Each addition changes cost, subnet planning, DNS, access control, Terraform
state and operational responsibilities. For Application Gateway to App Service
host-name, DNS, TLS and backend-probe configuration, see Microsoft's
[Application Gateway and App Service guidance](https://learn.microsoft.com/azure/application-gateway/configure-web-app).
For App Service private-link semantics, see
[App Service private endpoints](https://learn.microsoft.com/azure/app-service/overview-private-endpoint).
