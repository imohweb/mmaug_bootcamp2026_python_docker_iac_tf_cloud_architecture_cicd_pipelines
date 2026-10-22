#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?Missing AZURE_SUBSCRIPTION_ID}"
: "${AZURE_RESOURCE_GROUP:?Missing AZURE_RESOURCE_GROUP}"
: "${ACR_NAME:?Missing ACR_NAME}"
: "${BACKEND_WEB_APP_NAME:?Missing BACKEND_WEB_APP_NAME}"
: "${FRONTEND_WEB_APP_NAME:?Missing FRONTEND_WEB_APP_NAME}"
: "${BACKEND_IMAGE_REF:?Missing BACKEND_IMAGE_REF}"
: "${FRONTEND_IMAGE_REF:?Missing FRONTEND_IMAGE_REF}"
: "${SPECIALIST_API_TOKEN:?Missing SPECIALIST_API_TOKEN}"
[[ "$AZURE_RESOURCE_GROUP" == RG-MMAUG-Bootcamp ]] || { echo "Expected existing RG-MMAUG-Bootcamp" >&2; exit 1; }
[[ "$AZURE_SUBSCRIPTION_ID" =~ ^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$ ]] ||
  { echo "Invalid subscription ID" >&2; exit 1; }
[[ "$ACR_NAME" =~ ^[a-z0-9]{5,50}$ ]] || { echo "Invalid ACR_NAME" >&2; exit 1; }
[[ "$BACKEND_WEB_APP_NAME" =~ ^[a-zA-Z0-9-]{2,60}$ &&
   "$FRONTEND_WEB_APP_NAME" =~ ^[a-zA-Z0-9-]{2,60}$ &&
   "$BACKEND_WEB_APP_NAME" != "$FRONTEND_WEB_APP_NAME" ]] ||
  { echo "Two distinct valid web app names are required" >&2; exit 1; }
[[ "$BACKEND_IMAGE_REF" =~ ^${ACR_NAME}\.azurecr\.io/support-agent-backend@sha256:[a-f0-9]{64}$ &&
   "$FRONTEND_IMAGE_REF" =~ ^${ACR_NAME}\.azurecr\.io/support-agent-frontend@sha256:[a-f0-9]{64}$ ]] ||
  { echo "Both image references must be matching ACR repository digests" >&2; exit 1; }
[[ ${#SPECIALIST_API_TOKEN} -ge 32 && "$SPECIALIST_API_TOKEN" != REPLACE-* &&
   "$SPECIALIST_API_TOKEN" =~ ^[A-Za-z0-9._~+/=-]+$ ]] ||
  { echo "SPECIALIST_API_TOKEN must be random, at least 32 characters and URL-safe/base64" >&2; exit 1; }
for tool in az curl jq timeout; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
hostname_for() {
  local hostname
  hostname=$(az webapp show -g "$AZURE_RESOURCE_GROUP" -n "$1" --query defaultHostName -o tsv)
  [[ "$hostname" =~ ^[a-zA-Z0-9.-]+\.azurewebsites\.net$ ]] ||
    { echo "Invalid App Service hostname" >&2; return 1; }
  printf '%s' "$hostname"
}
backend_host=$(hostname_for "$BACKEND_WEB_APP_NAME")
frontend_host=$(hostname_for "$FRONTEND_WEB_APP_NAME")

# Avoid exposing the token in the Azure CLI process arguments.
settings_file=$(mktemp)
chmod 600 "$settings_file"
trap 'rm -f "$settings_file"' EXIT
jq -n 'env.SPECIALIST_API_TOKEN | {SPECIALIST_API_TOKEN: ., WEBSITES_PORT: "8000"}' > "$settings_file"
az webapp config appsettings set -g "$AZURE_RESOURCE_GROUP" -n "$BACKEND_WEB_APP_NAME" \
  --settings "@$settings_file" -o none
az webapp config appsettings set -g "$AZURE_RESOURCE_GROUP" -n "$FRONTEND_WEB_APP_NAME" \
  --settings WEBSITES_PORT=8000 "BACKEND_ORIGIN=https://$backend_host" -o none

release() {
  local app=$1 image=$2
  az webapp config set -g "$AZURE_RESOURCE_GROUP" -n "$app" \
    --generic-configurations '{"acrUseManagedIdentityCreds":true}' -o none
  az webapp log config -g "$AZURE_RESOURCE_GROUP" -n "$app" \
    --docker-container-logging filesystem -o none
  az webapp config container set -g "$AZURE_RESOURCE_GROUP" -n "$app" \
    --container-image-name "$image" --container-registry-url "https://$ACR_NAME.azurecr.io" -o none
  az webapp restart -g "$AZURE_RESOURCE_GROUP" -n "$app" -o none
}
get_json() {
  curl --silent --show-error --fail --connect-timeout 5 --max-time 20 "$@"
}
verify() {
  local url=$1 body
  for attempt in $(seq 1 30); do
    if body=$(get_json "$url/health") &&
       jq -e -s 'length == 1 and .[0].status == "ok"' <<< "$body" >/dev/null; then
      body=$(get_json "$url/api/config") || return 1
      jq -e -s 'length == 1 and (.[0].teams | type) == "array" and (.[0].teams | length) == 4 and
        (.[0].ai_mode == "off" or .[0].ai_mode == "agent" or .[0].ai_mode == "model")' \
        <<< "$body" >/dev/null || { echo "Invalid config JSON contract: $url" >&2; return 1; }
      body=$(printf 'header = "Authorization: Bearer %s"\n' "$SPECIALIST_API_TOKEN" |
        get_json --config - "$url/api/specialist/knowledge") || return 1
      jq -e -s 'length == 1 and (.[0].documents | type) == "array" and (.[0].documents | length) >= 1' \
        <<< "$body" >/dev/null || { echo "Invalid knowledge JSON contract: $url" >&2; return 1; }
      echo "Verified health, config and knowledge: $url"
      return 0
    fi
    sleep 5
  done
  echo "Health readiness failed: $url" >&2
  return 1
}
diagnostics() {
  echo "Deployment failed; new images may remain configured. Inspect both apps before rollback." >&2
  timeout 20s az webapp log tail -g "$AZURE_RESOURCE_GROUP" -n "$1" >&2 || true
}
release "$BACKEND_WEB_APP_NAME" "$BACKEND_IMAGE_REF"
verify "https://$backend_host" || { diagnostics "$BACKEND_WEB_APP_NAME"; exit 1; }
release "$FRONTEND_WEB_APP_NAME" "$FRONTEND_IMAGE_REF"
verify "https://$frontend_host" || { diagnostics "$FRONTEND_WEB_APP_NAME"; exit 1; }
html=$(get_json "https://$frontend_host/") || { diagnostics "$FRONTEND_WEB_APP_NAME"; exit 1; }
[[ "$html" == *'<div id="root">'* ]] || { echo "Frontend React shell missing" >&2; exit 1; }
echo "Released backend and frontend digests. Customer portal: https://$frontend_host/"
