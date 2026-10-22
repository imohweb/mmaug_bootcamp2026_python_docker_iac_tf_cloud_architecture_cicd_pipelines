#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export AZURE_SUBSCRIPTION_ID=12345678-1234-1234-1234-123456789abc
export AZURE_RESOURCE_GROUP=RG-MMAUG-Bootcamp ACR_NAME=demoregistry
export BACKEND_WEB_APP_NAME=demo-backend FRONTEND_WEB_APP_NAME=demo-frontend
export SPECIALIST_API_TOKEN="$(printf 't%.0s' {1..40})"
export BACKEND_IMAGE_REF="demoregistry.azurecr.io/support-agent-backend@sha256:$(printf 'a%.0s' {1..64})"
export FRONTEND_IMAGE_REF="demoregistry.azurecr.io/support-agent-frontend@sha256:$(printf 'b%.0s' {1..64})"
export MODE=success
export MOCK_LOG
MOCK_LOG=$(mktemp)
trap 'rm -f "$MOCK_LOG"' EXIT
az() {
  printf '%s\n' "$*" >> "$MOCK_LOG"
  case "$*" in
    'webapp show '*)
      [[ "$*" != *demo-backend* ]] || { echo demo-backend.azurewebsites.net; return; }
      echo demo-frontend.azurewebsites.net ;;
    'webapp restart '*) [[ "$MODE" != azure-failure ]] ;;
    'webapp config appsettings set '*)
      if [[ "$*" == *demo-backend* ]]; then
        local argument
        for argument; do
          if [[ "$argument" == @* ]]; then
            jq -e --arg token "$SPECIALIST_API_TOKEN" '.SPECIALIST_API_TOKEN == $token' "${argument#@}" >/dev/null
          fi
        done
      fi ;;
  esac
}
curl() {
  local url config
  for url; do :; done
  [[ "$url" == https://demo-backend.azurewebsites.net/* ||
     "$url" == https://demo-frontend.azurewebsites.net/* ]] || return 22
  [[ "$MODE" != unavailable ]] || return 22
  [[ "$MODE" != frontend-unavailable || "$url" != https://demo-frontend.azurewebsites.net/* ]] || return 22
  case "$url" in
    */health)
      if [[ "$MODE" == bad-health ]]; then echo '{"status":"bad"}'; else echo '{"status":"ok"}'; fi ;;
    */api/config)
      if [[ "$MODE" == bad-config ]]; then echo '{}'; else echo '{"ai_mode":"agent","teams":[{},{},{},{}]}'; fi ;;
    */api/specialist/knowledge)
      config=$(cat)
      [[ "$config" == "header = \"Authorization: Bearer $SPECIALIST_API_TOKEN\"" ]] || return 22
      if [[ "$MODE" == bad-knowledge ]]; then echo '{"documents":[]}'; else echo '{"documents":[{}]}'; fi ;;
    */) if [[ "$MODE" == bad-html ]]; then echo 'missing'; else echo '<div id="root"></div>'; fi ;;
    *) return 22 ;;
  esac
}
sleep() { :; }
timeout() { shift; "$@"; }
export -f az curl sleep timeout
count=0
expect() {
  local wanted=$1 output result=0
  output=$(bash scripts/deploy-azure.sh 2>&1) || result=$?
  if [[ "$wanted" == pass && "$result" != 0 || "$wanted" == fail && "$result" == 0 ]]; then
    printf 'FAIL (%s): %s\n' "$MODE" "$output" >&2; exit 1
  fi
  count=$((count + 1))
}
expect pass
grep -q -- "--container-image-name $BACKEND_IMAGE_REF" "$MOCK_LOG"
grep -q -- "--container-image-name $FRONTEND_IMAGE_REF" "$MOCK_LOG"
! grep -q "$SPECIALIST_API_TOKEN" "$MOCK_LOG"
! grep -q 'vm run-command' "$MOCK_LOG"
for MODE in azure-failure unavailable frontend-unavailable bad-health bad-config bad-knowledge bad-html; do
  export MODE
  expect fail
done
export MODE=success
saved=$FRONTEND_IMAGE_REF
export FRONTEND_IMAGE_REF=demoregistry.azurecr.io/support-agent-frontend:latest
expect fail
export FRONTEND_IMAGE_REF=$saved
saved=$BACKEND_IMAGE_REF
export BACKEND_IMAGE_REF="otherregistry.azurecr.io/support-agent-backend@sha256:$(printf 'a%.0s' {1..64})"
expect fail
export BACKEND_IMAGE_REF=$saved
saved=$AZURE_RESOURCE_GROUP
export AZURE_RESOURCE_GROUP=other-group
expect fail
export AZURE_RESOURCE_GROUP=$saved
saved=$FRONTEND_WEB_APP_NAME
export FRONTEND_WEB_APP_NAME=$BACKEND_WEB_APP_NAME
expect fail
export FRONTEND_WEB_APP_NAME=$saved
export SPECIALIST_API_TOKEN=short
expect fail
export SPECIALIST_API_TOKEN="REPLACE-$(printf 'x%.0s' {1..40})"
expect fail
export SPECIALIST_API_TOKEN="$(printf 'q%.0s' {1..40})\"invalid"
expect fail
echo "All $count dual-app deployment scenarios passed (offline)."
