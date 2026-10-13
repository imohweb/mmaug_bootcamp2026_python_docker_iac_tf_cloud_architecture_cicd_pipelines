#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${STATE_RG:?Set STATE_RG to a separate backend resource group.}"
: "${STATE_ACCOUNT:?Set a globally unique lowercase storage account name.}"
: "${LOCATION:?Set LOCATION to the desired Azure region.}"
: "${ARM_SUBSCRIPTION_ID:?Set ARM_SUBSCRIPTION_ID explicitly.}"
[[ "$STATE_ACCOUNT" =~ ^[a-z0-9]{3,24}$ ]] || {
  echo "STATE_ACCOUNT must contain 3-24 lowercase letters/digits." >&2
  exit 1
}

az account set --subscription "$ARM_SUBSCRIPTION_ID"
user_id=$(az ad signed-in-user show --query id -o tsv)
echo "Creates paid backend resources in $STATE_RG / $LOCATION."
read -r -p "Type CREATE to approve: " approval
[[ "$approval" == "CREATE" ]] || { echo "Cancelled." >&2; exit 1; }

az group create --name "$STATE_RG" --location "$LOCATION" --output none
az storage account create --name "$STATE_ACCOUNT" --resource-group "$STATE_RG" \
  --location "$LOCATION" --sku Standard_LRS --kind StorageV2 \
  --https-only true --min-tls-version TLS1_2 --allow-blob-public-access false \
  --allow-shared-key-access false --output none
account_id=$(az storage account show --name "$STATE_ACCOUNT" \
  --resource-group "$STATE_RG" --query id -o tsv)
az role assignment create --assignee-object-id "$user_id" --assignee-principal-type User \
  --role "Storage Blob Data Contributor" --scope "$account_id" --output none
echo "Wait for RBAC propagation, then run the documented container creation command."
echo "Storage account: $STATE_ACCOUNT | Container: tfstate | Key: mmaug/azure-demo.tfstate"
