#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"
command -v jq >/dev/null || { echo "Tests require jq." >&2; exit 1; }
export AZURE_SUBSCRIPTION_ID=12345678-1234-1234-1234-123456789abc
export AZURE_RESOURCE_GROUP=demo-rg ACR_NAME=demoregistry
export AZURE_WEB_APP_NAME=demo-web AZURE_VM_NAME=demo-vm
export IMAGE_REF="demoregistry.azurecr.io/launchpad@sha256:$(printf 'a%.0s' {1..64})"
unset VM_PUBLIC_IP
export MOCK_MODE=success FAIL_TARGET=all
passed=0

# Exported functions replace every Azure, HTTP, Docker and service operation.
az() {
  case "$*" in
    'webapp show '*) printf '%s\n' demo-web.azurewebsites.net ;;
    'vm show '*) printf '%s\n' 203.0.113.10 ;;
    'vm run-command invoke '*)
      case "$MOCK_MODE" in
        missing-marker)
          printf '%s\n' '{"value":[{"code":"ProvisioningState/succeeded","message":"script failed"}]}' ;;
        nonzero-exit)
          jq -n --arg marker "LAUNCHPAD_DEPLOY_OK_${IMAGE_REF##*:}" \
            '{value:[{exitCode:1,message:$marker}]}' ;;
        *)
          jq -n --arg marker "LAUNCHPAD_DEPLOY_OK_${IMAGE_REF##*:}" \
            '{value:[{message:("[stdout]\n" + $marker + "\n[stderr]\n")}]}' ;;
      esac ;;
    'webapp restart '*) [[ "$MOCK_MODE" != azure-failure ]] ;;
    *) : ;;
  esac
}

curl() {
  local url target mode
  for url; do :; done
  case "$url" in
    https://demo-web.azurewebsites.net/*) target=web ;;
    http://203.0.113.10/*) target=vm ;;
    http://127.0.0.1/*) target=guest ;;
    *) echo "Unexpected mock URL: $url" >&2; return 1 ;;
  esac
  mode=success
  if [[ "$FAIL_TARGET" == all || "$FAIL_TARGET" == "$target" ]]; then
    mode=$MOCK_MODE
  fi
  [[ "$mode" != readiness-failure ]] || return 22
  if [[ "$url" == */health ]]; then
    case "$mode" in
      health-malformed) printf '%s\n' '<html>not JSON</html>' ;;
      health-wrong) printf '%s\n' '{"status":"not-ok"}' ;;
      health-empty) : ;;
      health-multiple) printf '%s\n' '{"status":"not-ok"}' '{"status":"ok"}' ;;
      *) printf '%s\n' '{"status":"ok"}' ;;
    esac
  else
    [[ "$url" == */sum?values=5,10,15 ]] || return 1
    case "$mode" in
      sum-malformed) printf '%s\n' '<html>not JSON</html>' ;;
      sum-wrong-total) printf '%s\n' '{"total":31,"average":10}' ;;
      sum-wrong-average) printf '%s\n' '{"total":30,"average":11}' ;;
      sum-string-average) printf '%s\n' '{"total":30,"average":"10"}' ;;
      sum-string-total) printf '%s\n' '{"total":"30","average":10}' ;;
      sum-missing-average) printf '%s\n' '{"total":30}' ;;
      sum-array) printf '%s\n' '[{"total":30,"average":10}]' ;;
      sum-empty) : ;;
      sum-multiple) printf '%s\n' '{"total":31,"average":11}' '{"total":30,"average":10}' ;;
      *) printf '%s\n' '{"total":30,"average":10}' ;;
    esac
  fi
}

sleep() { :; }
timeout() { shift; "$@"; }
docker() {
  case "$*" in
    'container inspect launchpad') return 1 ;;
    'inspect --format '*) printf '%s\n' "$IMAGE_REF" ;;
    *) : ;;
  esac
}
systemctl() { :; }
journalctl() { :; }
export -f az curl sleep timeout docker systemctl journalctl

expect_pass() {
  local output
  if output=$(bash scripts/deploy-azure.sh 2>&1); then
    [[ "$output" == *'Verified health and sum JSON contracts: https://demo-web.azurewebsites.net'* &&
      "$output" == *'Verified health and sum JSON contracts: http://203.0.113.10'* ]] ||
      { echo "FAIL: both endpoint verifications must run" >&2; exit 1; }
    echo "PASS: $1"
    passed=$((passed + 1))
  else
    printf 'FAIL: %s\n%s\n' "$1" "$output" >&2
    exit 1
  fi
}

expect_fail() {
  local output
  if output=$(bash scripts/deploy-azure.sh 2>&1); then
    echo "FAIL: $1 unexpectedly succeeded" >&2
    exit 1
  fi
  if [[ -n "${2:-}" && "$output" != *"$2"* ]]; then
    printf 'FAIL: %s did not report expected diagnostic %s\n%s\n' "$1" "$2" "$output" >&2
    exit 1
  fi
  echo "PASS: $1 rejected"
  passed=$((passed + 1))
}

expect_pass 'both public health and sum contracts, queried IP'
export VM_PUBLIC_IP=203.0.113.10
expect_pass 'both public contracts, explicit IP'
unset VM_PUBLIC_IP
for mode in missing-marker nonzero-exit azure-failure readiness-failure; do
  export MOCK_MODE=$mode
  expect_fail "$mode"
done
export MOCK_MODE=success
saved_image=$IMAGE_REF
export IMAGE_REF='demoregistry.azurecr.io/launchpad:latest'
expect_fail 'mutable image tag'
export IMAGE_REF="otherregistry.azurecr.io/launchpad@${saved_image##*@}"
expect_fail 'different registry'
export IMAGE_REF="$saved_image;echo unsafe"
expect_fail 'shell metacharacters'
export IMAGE_REF=$saved_image
unset AZURE_RESOURCE_GROUP
expect_fail 'missing required environment variable'
export AZURE_RESOURCE_GROUP=demo-rg

# Root is the only guest prerequisite bypassed, in-memory; files are unchanged.
guest_script=$(sed 's/\[\[ "$EUID" -eq 0 \]\]/true/' scripts/deploy-vm.sh)
if bash -s -- "$IMAGE_REF" "$ACR_NAME" <<< "$guest_script" |
  grep -Fxq "LAUNCHPAD_DEPLOY_OK_${IMAGE_REF##*:}"; then
  echo 'PASS: guest pull/run/nginx health/success marker'
  passed=$((passed + 1))
else
  echo 'FAIL: mocked guest deployment' >&2
  exit 1
fi
export MOCK_MODE=readiness-failure
if bash -s -- "$IMAGE_REF" "$ACR_NAME" <<< "$guest_script" >/dev/null 2>&1; then
  echo 'FAIL: guest readiness unexpectedly succeeded' >&2
  exit 1
else
  echo 'PASS: guest bounded readiness failure'
  passed=$((passed + 1))
fi

for target in web vm; do
  export FAIL_TARGET=$target
  for mode in health-malformed health-wrong health-empty health-multiple; do
    export MOCK_MODE=$mode
    expect_fail "$target $mode" 'Invalid health JSON contract:'
  done
  for mode in sum-malformed sum-wrong-total sum-wrong-average sum-string-average sum-string-total sum-missing-average sum-array sum-empty sum-multiple; do
    export MOCK_MODE=$mode
    expect_fail "$target $mode" 'Invalid sum JSON contract:'
  done
done
echo "All $passed deployment regression scenarios passed (no live Azure/HTTP/Docker calls)."
