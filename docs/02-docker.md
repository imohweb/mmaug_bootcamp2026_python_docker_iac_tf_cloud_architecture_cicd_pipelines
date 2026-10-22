# Docker: package the customer-support agent

Run repository commands from the project root unless a step says otherwise.
The default image includes Flask and the built React portal for the local
foundations lab. Cloud delivery builds separate backend and frontend targets.

## Image, container and build context

- **Dockerfile:** build instructions.
- **Build context:** files available to the builder; here it is `support-agent/`.
- **Image:** layered, packaged filesystem and runtime configuration.
- **Container:** a process created from an image, with a writable layer.
- **Registry:** distributes images; Azure Container Registry (ACR) is used in
  the Azure pipeline.
- **Tag:** a mutable label; a digest identifies immutable image content.

Docker Desktop supplies Linux container support on macOS and Windows. Docker
socket access is privileged; do not give it to untrusted code.

## Multi-target Dockerfile

`support-agent/Dockerfile` uses `node:22-alpine` as the frontend-build stage:
copy the npm manifests, run `npm ci`, copy the React source and run
`npm run build`. The second stage starts from `python:3.12-slim`, installs only
the backend requirements, copies the API and includes Markdown seed files for
offline/local storage. The backend target excludes the React build; a separate
frontend target serves React through a non-root Node static server/API proxy.
The final combined target adds React assets back to Python for the original
one-container lab. Node/npm do not ship in the Python runtime.

```bash
docker build --target backend -t mmaug-support-agent-backend:1.0 support-agent
docker build --target frontend -t mmaug-support-agent-frontend:1.0 support-agent
```

For a local rehearsal of the cloud split, use
`docker compose -f support-agent/compose.split.yaml up --build -d` from the repo
root after exporting a specialist token. The frontend proxies `/api` and
`/health` to `BACKEND_ORIGIN=http://backend:8000`; Azure uses the HTTPS backend
origin. Stop with the same Compose file and `down` (without `-v` to retain data).

The runtime sets `PORT=8000`, `DATA_DIR=/data`, and paths for the UI and
knowledge seed. It runs Gunicorn as non-root uid 10001, exposes container port
8000, and has a `/health` Docker health check. The `/data` mount keeps local
tickets across container replacement. `EXPOSE` documents an internal port; it
does not publish it. `.dockerignore` excludes local virtual environments,
node_modules, build output, local secrets and Terraform files from the context.

```bash
cd support-agent
docker version
docker info
docker build -t mmaug-support-agent:1.0 .
docker image inspect mmaug-support-agent:1.0
docker run -d --name support-agent-manual \
  -p 127.0.0.1:8080:8000 \
  -e SPECIALIST_API_TOKEN="$SPECIALIST_API_TOKEN" \
  -v support-agent-manual-data:/data \
  mmaug-support-agent:1.0
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/api/config
docker inspect --format '{{.State.Health.Status}}' support-agent-manual
docker exec support-agent-manual id
```

Set `SPECIALIST_API_TOKEN` in your shell first; do not put a real token in the
Dockerfile or commit it. The `-p` order is host IP:host port:container port.
The container should run with uid 10001. A running container may still be
starting or unhealthy; inspect `docker logs support-agent-manual`.

```bash
docker stop support-agent-manual
docker rm support-agent-manual
```

Removing a container does not remove a separately named volume or image. Inspect
objects before removing only those created for this lab; avoid broad prune
commands.

## Compose

`support-agent/compose.yaml` builds from the current folder, runs the same
image, binds only to `127.0.0.1:8090`, and passes the specialist token from the
environment. Its named `support-data` volume persists `/data`.

```bash
cd support-agent
export SPECIALIST_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
# Avoid printing resolved Compose configuration: it contains the token.
docker compose up -d --build
curl -fsS http://127.0.0.1:8090/health
docker compose logs
docker compose down
```

`down` removes Compose containers/network, but preserves named volumes unless
`--volumes` is requested. Do not let Compose and Terraform manage the same
container independently.

## Local Docker-provider Terraform lab

The small root at `support-agent/terraform` manages a local Docker image
reference, container, localhost port and named data volume. Build the image
first from `support-agent/`, then supply the sensitive token through an
environment variable (never a committed `.tfvars` file):

```bash
cd support-agent
docker build -t mmaug-support-agent:1.0 .
export SPECIALIST_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export TF_VAR_specialist_token="$SPECIALIST_API_TOKEN"
cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out=local.tfplan
# Review the resources and bind address before applying.
terraform apply local.tfplan
terraform output -raw app_url
curl -fsS http://127.0.0.1:8080/health
terraform plan -destroy -out=local-cleanup.tfplan
# Review that only this local lab is managed.
terraform apply local-cleanup.tfplan
unset TF_VAR_specialist_token SPECIALIST_API_TOKEN
```

Terraform marking the token sensitive masks normal CLI output; it does not
remove it from Terraform state. Protect state and do not publish it. The lab's
image is retained locally; remove it only when no longer needed.

## Troubleshooting by layer

| Symptom | Check |
| --- | --- |
| Cannot connect to daemon | Start Docker Desktop; inspect `docker info` and context. |
| Name already used | Inspect the named lab container before removing it. |
| Port allocated | Identify the owner or select another host port. |
| HTTP connection refused | Check port mapping, container logs and health. |
| Specialist console unavailable | Confirm a valid token was supplied at runtime. |
| Image architecture error | Build for a platform supported by the host/target. |
| Azure image pull denied | Check App Service managed identity and ACR `AcrPull`. |

References: [Docker get started](https://docs.docker.com/get-started/),
[Dockerfile reference](https://docs.docker.com/reference/dockerfile/),
[Compose](https://docs.docker.com/compose/).
