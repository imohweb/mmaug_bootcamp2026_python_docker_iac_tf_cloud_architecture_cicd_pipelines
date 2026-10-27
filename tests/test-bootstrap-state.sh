#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export ARM_SUBSCRIPTION_ID=synthetic-subscription STATE_ACCOUNT=syntheticstorage MODE=existing
az() {
  case "$*" in
    'account show '*) echo synthetic-subscription ;;
    'group show '*) echo northeurope ;;
    'storage account list '*) [[ "$MODE" != new ]] && echo syntheticstorage; return 0 ;;
    'storage account show '*)
      if [[ "$MODE" == insecure ]]; then echo '{}'
      else echo '{"allowSharedKeyAccess":false,"allowBlobPublicAccess":false,"enableHttpsTrafficOnly":true,"minimumTlsVersion":"TLS1_2"}'; fi ;;
    'storage container create '*)
      [[ "$*" == *'--auth-mode login --public-access off'* ]] || {
        echo "Container creation must use Entra authentication and private access" >&2; return 1;
      }
      [[ "$MODE" != denied ]] ;;
    'storage account create '*)
      [[ "$*" == 'storage account create -g RG-MMAUG-Bootcamp -n syntheticstorage -l northeurope --sku Standard_LRS --kind StorageV2 --https-only true --min-tls-version TLS1_2 --allow-blob-public-access false --allow-shared-key-access false -o none' ]] || {
        echo "Unexpected storage creation arguments: $*" >&2; return 1;
      } ;;
    'storage account blob-service-properties update '*) return 0 ;;
    *) echo "Unexpected Azure operation: $*" >&2; return 1 ;;
  esac
}
export -f az
for MODE in existing new; do export MODE; bash scripts/bootstrap-state.sh >/dev/null; done
for MODE in insecure denied; do
  export MODE
  if bash scripts/bootstrap-state.sh >/dev/null 2>&1; then echo "Expected failure: $MODE" >&2; exit 1; fi
done
export STATE_ACCOUNT='invalid;name'
if bash scripts/bootstrap-state.sh >/dev/null 2>&1; then exit 1; fi
echo "All 5 bootstrap scenarios passed (offline)."
