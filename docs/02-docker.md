# Docker, completely broken into responsibilities

Run commands from `launchpad-lab`, unless a step says otherwise.

## Recipe, package, instance

- **Dockerfile:** build instructions.
- **Build context:** files available to the builder; the final `.` means here.
- **Image:** layered packaged filesystem and runtime configuration.
- **Container:** a process instance created from an image, plus writable layer.
- **Registry:** distributes images; ACR will be ours in the Azure extension.
- **Tag:** mutable label; a digest identifies image content.

Linux containers share their host's Linux kernel. Docker Desktop typically
supplies a Linux VM on macOS/Windows. CPU architecture still matters.
Docker socket/group access is privileged; do not give it to untrusted code.

## Every Dockerfile instruction

| Instruction | Meaning in this application |
|---|---|
| `FROM python:3.12-slim` | Python interpreter plus a minimal Debian runtime. A tag is not an immutable digest. |
| `WORKDIR /app` | Establish the directory for later commands and startup. |
| `ENV ...` | Disable bytecode files, flush logs, document default port 8000. |
| `RUN groupadd ... && useradd ...` | Build-time creation of uid/gid 10001; failure stops the build. |
| `COPY requirements.txt .` | Copy the dependency manifest before frequently changing source for caching. |
| `RUN pip install --no-cache-dir -r requirements.txt` | Install Flask/Gunicorn, Foundry/OpenAI SDKs, identity and dotenv dependencies into the image, not the host. |
| `COPY --chown=app:app app.py .` | Package source with intended ownership. |
| `COPY --chown=app:app ai_demo.py .` | Package the optional model/agent SDK helpers; no credentials are copied. |
| `COPY ... templates/ ...` and `COPY ... static/ ...` | Package browser assets required by `/ui`. |
| `USER app` | Run the application as non-root. |
| `EXPOSE 8000` | Document internal port. This does **not** publish it on the host. |
| `HEALTHCHECK ...` | Probe `/health` internally every ten seconds, three-second timeout, startup grace, repeated-failure threshold. Backslashes continue the Dockerfile instruction. The Python request command needs no curl package inside the image. |
| `CMD ["gunicorn", ... "app:app"]` | Runtime startup in exec form: module `app`, Flask object `app`, two workers, all interfaces on internal 8000, access/error logs to standard streams. |

`RUN` runs during build, whereas `CMD` sets default container startup. `ENTRYPOINT`
defines a fixed executable when used; it is not needed here. Each build layer
can be cached; changing a layer invalidates following layers. A multi-stage
build separates build tools from runtime output when that actually helps; our
small app does not need an artificial second stage.

`.dockerignore` excludes local venvs, caches, Git metadata, `.env`, `.env-local`, tests and
Terraform artifacts from the build context. It is not a universal secret scanner.

The [optional AI demo](06-foundry-demo.md) provides the complete local Docker
Desktop build/run, ACR login/tag/push, immutable image reference and
managed-identity App Service deployment sequence.

## Build and verify

```bash
docker version
docker info
docker build -t mmaug-launchpad:1.0 .
docker image ls mmaug-launchpad
docker image inspect mmaug-launchpad:1.0
docker run -d --name mmaug-launchpad-manual -p 127.0.0.1:8080:8000 -e "APP_MESSAGE=Hello from Docker!" mmaug-launchpad:1.0
curl -fsS http://127.0.0.1:8080/health
curl -fsS "http://127.0.0.1:8080/sum?values=5,10,15"
```

Open <http://127.0.0.1:8080/ui>. `-d` detaches; `--name` names this instance;
`-p` means host IP : host port : container port; `-e` supplies public configuration.
The Gunicorn bind is inside the container. Host localhost and container
localhost are not the same network namespace.

```bash
docker ps --filter name=mmaug-launchpad-manual
docker logs mmaug-launchpad-manual
docker inspect --format '{{.State.Health.Status}}' mmaug-launchpad-manual
docker inspect --format '{{json .State.Health}}' mmaug-launchpad-manual
docker exec mmaug-launchpad-manual id
docker stats --no-stream mmaug-launchpad-manual
```

Wait for `healthy` and verify uid 10001. A running container may still be
unready. Docker records unhealthy status; it does not auto-restart solely
because of the health check.

```bash
docker stop mmaug-launchpad-manual
docker start mmaug-launchpad-manual
docker stop mmaug-launchpad-manual
docker rm mmaug-launchpad-manual
```

`start` reuses a stopped container, whereas `run` creates another one.
Keep the image for the Terraform lab. Do not run broad `docker system prune`.

## Compose comparison

```bash
docker compose config
docker compose -p mmaug-launchpad-lab up -d --build
curl -fsS http://127.0.0.1:8090/health
docker compose -p mmaug-launchpad-lab logs
docker compose -p mmaug-launchpad-lab down
```

The supplied YAML defines one service, its image/build, public greeting and host
port 8090. Project naming scopes resources. `down` removes that project's
container/network, not its image by default. Do not have Compose and Terraform
independently own the same container.

## Persistent data and networks

The app is stateless. Container writable-layer files disappear on removal;
named volumes/bind mounts persist independently according to their lifecycle.
Do not edit production source inside a running container. Edit, test, rebuild,
release and replace. User-defined networks let containers reach one another by
service names; they do not make every port public. No database/volume is needed here.

Useful read-only inspection commands, while the manual container exists:

```bash
docker network ls
docker volume ls
docker port mmaug-launchpad-manual
docker inspect --format '{{json .NetworkSettings.Networks}}' mmaug-launchpad-manual
docker image history mmaug-launchpad:1.0
```

`network ls` and `volume ls` show existing objects without deleting or changing
them. `port` confirms publishing; network inspection shows the instance's
network attachment; image history describes build layers. Do not infer that
a named volume has a backup merely because it appears in the list.

## Registry handoff in Azure

After provisioning ACR and granting the publishing identity `AcrPush`:

```bash
az acr login --name "$ACR_NAME"
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
docker build --platform linux/amd64 -t "$ACR_LOGIN_SERVER/launchpad:bootstrap" .
docker push "$ACR_LOGIN_SERVER/launchpad:bootstrap"
```

The explicit platform matches the demo VM's amd64 architecture, even if built
from an ARM laptop. Pipelines publish unique release tags and deploy the same
image digest to both targets. Runtime identities use `AcrPull`, not admin passwords.

## Troubleshooting by layer

| Symptom | Check / correction |
|---|---|
| Cannot connect to daemon | Start chosen Docker runtime; `docker info`; inspect active context. |
| Name already used | Inspect only your named lab container before removing it. |
| Port allocated | Identify the owner or deliberately choose another host port. |
| Connection refused | Publishing configuration, Gunicorn bind and application logs. |
| Unhealthy | Inspect health probe output; keep internal 8000 for this lab. |
| HTTP 400 | Network worked; fix input contract, not Docker. |
| Image pull denied | Local image absent or registry identity lacks correct pull role. |
| exec format error | Build/pull an image compatible with the host CPU architecture. |

References: [Docker get started](https://docs.docker.com/get-started/),
[Dockerfile reference](https://docs.docker.com/reference/dockerfile/),
[Compose](https://docs.docker.com/compose/),
[ACR managed identity](https://learn.microsoft.com/azure/container-registry/container-registry-authentication-managed-identity).
