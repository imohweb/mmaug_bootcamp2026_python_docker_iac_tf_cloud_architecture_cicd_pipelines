"""Credential for Terraform's data-plane bridge scripts.

In GitHub Actions, `azure/login` exchanges a single OIDC assertion that expires
after a few minutes, so long applies (for example, a slow Search creation)
leave the Azure CLI unable to acquire new tokens. When the Actions OIDC
endpoint is available, request a fresh assertion for every Entra exchange.
Elsewhere, keep the existing DefaultAzureCredential behaviour.
"""

import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from azure.identity import ClientAssertionCredential, DefaultAzureCredential

AUDIENCE = "api://AzureADTokenExchange"


def _first_setting(*names):
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _github_assertion(url, token):
    def fetch():
        separator = "&" if "?" in url else "?"
        request = Request(
            f"{url}{separator}audience={quote(AUDIENCE, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urlopen(request, timeout=30) as response:
            value = json.load(response).get("value", "")
        if not value:
            raise RuntimeError("GitHub Actions did not return an OIDC token.")
        return value

    return fetch


def provisioning_credential():
    url = os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
    token = os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
    client_id = _first_setting("ARM_CLIENT_ID", "AZURE_CLIENT_ID")
    tenant_id = _first_setting("ARM_TENANT_ID", "AZURE_TENANT_ID")
    if url and token and client_id and tenant_id:
        return ClientAssertionCredential(tenant_id, client_id, _github_assertion(url, token))
    return DefaultAzureCredential()
