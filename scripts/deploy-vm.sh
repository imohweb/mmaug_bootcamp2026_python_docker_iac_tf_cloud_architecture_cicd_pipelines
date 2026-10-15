#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

# Run Command executes this script as root; its named parameters arrive as $1/$2.
image_ref=${1:?Expected immutable image reference as argument 1}
acr_name=${2:?Expected ACR name as argument 2}
[[ "$acr_name" =~ ^[a-zA-Z0-9]{5,50}$ ]] || { echo "Invalid ACR name" >&2; exit 1; }
[[ "$image_ref" =~ ^[a-zA-Z0-9]+\.azurecr\.io/launchpad@sha256:[a-f0-9]{64}$ ]] ||
  { echo "Expected registry.azurecr.io/launchpad@sha256:<64 hex>" >&2; exit 1; }
registry_name=$(printf '%s' "$acr_name" | tr '[:upper:]' '[:lower:]')
[[ "${image_ref%%.*}" == "$registry_name" ]] || { echo "Image registry does not match ACR name" >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || { echo "Run this script through Azure VM Run Command (root)." >&2; exit 1; }
for tool in cloud-init timeout; do
  command -v "$tool" >/dev/null || { echo "Missing VM bootstrap prerequisite: $tool" >&2; exit 1; }
done
if ! timeout 300s cloud-init status --wait; then
  echo "VM cloud-init did not complete successfully within 300 seconds; inspect /var/log/cloud-init-output.log." >&2
  exit 1
fi
for tool in az docker curl; do
  command -v "$tool" >/dev/null || { echo "Missing VM prerequisite: $tool (check cloud-init)." >&2; exit 1; }
done
systemctl is-active --quiet docker
systemctl is-active --quiet nginx

az login --identity --output none
az acr login --name "$acr_name" --output none
docker pull "$image_ref" >/dev/null

if docker container inspect launchpad >/dev/null 2>&1; then
  docker rm --force launchpad >/dev/null
fi
docker run --detach --name launchpad --restart unless-stopped \
  --publish 127.0.0.1:8000:8000 "$image_ref" >/dev/null
[[ "$(docker inspect --format '{{.Config.Image}}' launchpad)" == "$image_ref" ]] ||
  { echo "Running container image differs from requested digest" >&2; exit 1; }

for attempt in $(seq 1 30); do
  if body=$(curl --silent --show-error --fail --connect-timeout 2 --max-time 5 http://127.0.0.1/health 2>/dev/null) &&
    grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<< "$body"; then
    echo "LAUNCHPAD_DEPLOY_OK_${image_ref##*:}"
    exit 0
  fi
  sleep 2
done
echo "VM readiness failed after 30 attempts; container and nginx diagnostics:" >&2
docker logs --tail 100 launchpad >&2 || true
journalctl --unit nginx --no-pager --lines 30 >&2 || true
exit 1
