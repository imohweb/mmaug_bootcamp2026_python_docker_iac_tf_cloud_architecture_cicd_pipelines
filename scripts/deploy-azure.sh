#!/usr/bin/env bash
set -euo pipefail

for name in AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP ACR_NAME AZURE_WEB_APP_NAME AZURE_VM_NAME IMAGE_REF; do
  [[ -n "${!name:-}" ]] || { echo "Missing required environment variable: $name" >&2; exit 1; }
done
[[ "$AZURE_SUBSCRIPTION_ID" =~ ^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$ ]] ||
  { echo "Invalid subscription ID" >&2; exit 1; }
[[ "$AZURE_RESOURCE_GROUP" =~ ^[a-zA-Z0-9_().-]{1,90}$ ]] || { echo "Invalid resource group name" >&2; exit 1; }
[[ "$ACR_NAME" =~ ^[a-zA-Z0-9]{5,50}$ ]] || { echo "Invalid ACR_NAME" >&2; exit 1; }
[[ "$AZURE_WEB_APP_NAME" =~ ^[a-zA-Z0-9-]{2,60}$ ]] || { echo "Invalid web app name" >&2; exit 1; }
[[ "$AZURE_VM_NAME" =~ ^[a-zA-Z0-9_.-]{1,64}$ ]] || { echo "Invalid VM name" >&2; exit 1; }
[[ "$IMAGE_REF" =~ ^[a-zA-Z0-9]+\.azurecr\.io/launchpad@sha256:[a-f0-9]{64}$ ]] ||
  { echo "IMAGE_REF must be registry.azurecr.io/launchpad@sha256:<64 hex>" >&2; exit 1; }
registry_name=$(printf '%s' "$ACR_NAME" | tr '[:upper:]' '[:lower:]')
[[ "${IMAGE_REF%%.*}" == "$registry_name" ]] || { echo "Image registry does not match ACR_NAME" >&2; exit 1; }
for tool in az curl jq timeout; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

az webapp config set --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" \
  --generic-configurations '{"acrUseManagedIdentityCreds":true}' --output none
az webapp config appsettings set --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" \
  --settings WEBSITES_PORT=8000 --output none
az webapp log config --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" \
  --docker-container-logging filesystem --output none
az webapp config container set --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" \
  --container-image-name "$IMAGE_REF" \
  --container-registry-url "https://${IMAGE_REF%%/*}" --output none
az webapp restart --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" --output none

hostname=$(az webapp show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" \
  --query defaultHostName --output tsv)
[[ "$hostname" =~ ^[a-zA-Z0-9.-]+\.azurewebsites\.net$ ]] || { echo "Invalid web app hostname" >&2; exit 1; }

check_contract() {
  local url=$1 body sum_body attempt
  for attempt in $(seq 1 30); do
    if body=$(curl --silent --show-error --fail --connect-timeout 5 --max-time 10 "$url/health" 2>/dev/null); then
      if ! jq -e -s 'length == 1 and (.[0] | type) == "object" and .[0].status == "ok"' <<< "$body" >/dev/null; then
        echo "Invalid health JSON contract: $url/health" >&2
        printf 'Response (first 500 characters): %.500s\n' "$body" >&2
        return 1
      fi
      if sum_body=$(curl --silent --show-error --fail --connect-timeout 5 --max-time 10 "$url/sum?values=5,10,15" 2>/dev/null); then
        if ! jq -e -s 'length == 1 and (.[0] | type) == "object" and (.[0].total | type) == "number" and .[0].total == 30 and (.[0].average | type) == "number" and .[0].average == 10' <<< "$sum_body" >/dev/null; then
          echo "Invalid sum JSON contract: $url/sum?values=5,10,15" >&2
          printf 'Response (first 500 characters): %.500s\n' "$sum_body" >&2
          return 1
        fi
        echo "Verified health and sum JSON contracts: $url"
        return 0
      fi
    fi
    sleep 5
  done
  echo "Readiness failed after 30 attempts: $url/health" >&2
  return 1
}

if ! check_contract "https://$hostname"; then
  echo "Inspect App Service Log stream / container logs in the Azure portal." >&2
  timeout 30s az webapp log tail --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_WEB_APP_NAME" >&2 || true
  exit 1
fi

response=$(az vm run-command invoke --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_VM_NAME" \
  --command-id RunShellScript --scripts "@$script_dir/deploy-vm.sh" \
  --parameters "imageRef=$IMAGE_REF" "acrName=$ACR_NAME" --output json)
messages=$(jq -r '.value[]?.message // empty' <<< "$response")
marker="LAUNCHPAD_DEPLOY_OK_${IMAGE_REF##*:}"
# Azure's provisioning status alone does not prove that the guest script succeeded.
if ! grep -Fxq -- "$marker" <<< "$messages" ||
  ! jq -e '[.value[]? | select(has("exitCode")) | .exitCode | tonumber] | all(. == 0)' <<< "$response" >/dev/null; then
  echo "VM deployment did not return its success marker. Guest output:" >&2
  printf '%s\n' "$messages" >&2
  exit 1
fi

vm_ip=${VM_PUBLIC_IP:-}
if [[ -z "$vm_ip" ]]; then
  vm_ip=$(az vm show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_VM_NAME" \
    --show-details --query publicIps --output tsv)
fi
[[ "$vm_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || { echo "Expected one VM public IPv4 address" >&2; exit 1; }
if ! check_contract "http://$vm_ip"; then
  az vm run-command invoke --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_VM_NAME" \
    --command-id RunShellScript \
    --scripts 'docker logs --tail 100 launchpad 2>&1; journalctl --unit nginx --no-pager --lines 30' \
    --query 'value[].message' --output tsv >&2 || true
  exit 1
fi
echo "Released $IMAGE_REF to https://$hostname/ui and http://$vm_ip/ui"
