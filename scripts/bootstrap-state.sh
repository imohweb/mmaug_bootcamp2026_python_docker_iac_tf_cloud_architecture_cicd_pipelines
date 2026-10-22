#!/usr/bin/env bash
# Required: ARM_SUBSCRIPTION_ID, STATE_ACCOUNT. Optional: STATE_RG (fixed target).
# Administrator must grant resource Contributor and Blob Data Contributor first.
# This script never grants itself roles or enables storage keys.
set -euo pipefail
: "${ARM_SUBSCRIPTION_ID:?Set ARM_SUBSCRIPTION_ID}"
: "${STATE_ACCOUNT:?Set STATE_ACCOUNT}"
STATE_RG=${STATE_RG:-RG-MMAUG-Bootcamp}
[[ "$STATE_RG" == RG-MMAUG-Bootcamp ]] || { echo "Expected RG-MMAUG-Bootcamp" >&2; exit 1; }
[[ "$STATE_ACCOUNT" =~ ^[a-z0-9]{3,24}$ ]] || { echo "Invalid storage name" >&2; exit 1; }
current=$(az account show --query id -o tsv)
[[ "$current" == "$ARM_SUBSCRIPTION_ID" ]] || { echo "Azure login subscription mismatch" >&2; exit 1; }
location=$(az group show -n "$STATE_RG" --query location -o tsv)
accounts=$(az storage account list -g "$STATE_RG" --query "[?name=='$STATE_ACCOUNT'].name" -o tsv)
if [[ -z "$accounts" ]]; then
  az storage account create -g "$STATE_RG" -n "$STATE_ACCOUNT" -l "$location" \
    --sku Standard_LRS --kind StorageV2 --https-only true --min-tls-version TLS1_2 \
    --allow-blob-public-access false --allow-shared-key-access false \
    --default-to-oauth-authentication true -o none
fi
properties=$(az storage account show -g "$STATE_RG" -n "$STATE_ACCOUNT" -o json)
jq -e '.allowSharedKeyAccess == false and .allowBlobPublicAccess == false and
  .enableHttpsTrafficOnly == true and .minimumTlsVersion == "TLS1_2"' \
  <<< "$properties" >/dev/null || { echo "Existing storage account fails security prerequisites" >&2; exit 1; }
for container in tfstate knowledge tickets; do
  if ! az storage container create --account-name "$STATE_ACCOUNT" -n "$container" \
    --auth-mode login --public-access off -o none; then
    echo "Bootstrap requires Storage Blob Data Contributor; ask an administrator (RBAC propagation may take time)." >&2
    exit 1
  fi
done
az storage account blob-service-properties update -g "$STATE_RG" --account-name "$STATE_ACCOUNT" \
  --enable-versioning true --enable-delete-retention true --delete-retention-days 7 \
  --enable-container-delete-retention true --container-delete-retention-days 7 -o none
echo "Bootstrap complete: private tfstate, knowledge and tickets containers."
