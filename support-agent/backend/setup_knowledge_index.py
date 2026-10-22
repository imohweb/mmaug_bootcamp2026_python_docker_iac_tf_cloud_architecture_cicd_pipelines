"""Seed Blob knowledge, refresh its index, and connect a real Foundry IQ knowledge base.

Run after Terraform using the pipeline's federated Azure identity. No keys are used.
API contracts: https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index
https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect
"""

import argparse
import json
import logging
import os
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from ai_client import required_setting
from knowledge import seed_knowledge
from storage import BlobStore

API_VERSION = "2026-08-01-preview"
INDEX_API_VERSION = "2024-07-01"
log = logging.getLogger(__name__)


class AzureRest:
    def __init__(self, credential):
        self.credential = credential

    def request(self, method, url, body=None, *, scope="https://search.azure.com/.default"):
        data = None if body is None else json.dumps(body).encode("utf-8")
        for attempt in range(12):
            token = self.credential.get_token(scope).token
            request = Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            })
            try:
                with urlopen(request, timeout=90) as response:
                    content = response.read()
                    return json.loads(content) if content else {}
            except HTTPError as error:
                indexer_busy = error.code == 409 and method == "POST" and "/indexers/" in url and "/run?" in url
                if (error.code not in (403, 429, 500, 502, 503, 504) and not indexer_busy) or attempt == 11:
                    # Do not echo response bodies that could contain source content or credentials.
                    raise RuntimeError(f"Azure {method} failed with HTTP {error.code}: {url}") from error
                log.warning("Azure returned %s; retrying in 10s (%s/12).", error.code, attempt + 1)
                time.sleep(10)
        raise RuntimeError("Azure retry budget exhausted.")


def field(name, *, searchable=False, key=False):
    result = {"name": name, "type": "Edm.String", "searchable": searchable, "retrievable": True}
    if key:
        result["key"] = True
    return result


def index_definition(name):
    return {
        "name": name,
        "fields": [
            field("id", key=True), field("content", searchable=True),
            field("metadata_storage_name", searchable=True), field("metadata_storage_path"),
        ],
        "semantic": {"defaultConfiguration": "support-semantic", "configurations": [{
            "name": "support-semantic",
            "prioritizedFields": {
                "titleField": {"fieldName": "metadata_storage_name"},
                "prioritizedContentFields": [{"fieldName": "content"}],
                "prioritizedKeywordsFields": [],
            },
        }]},
    }


def wait_for_indexer(rest, status_url, *, previous_start=None, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = rest.request("GET", status_url)
        if status.get("status") == "error":
            raise RuntimeError("Knowledge indexer is in an error state.")
        result = status.get("lastResult") or {}
        if result.get("startTime") and result.get("startTime") != previous_start:
            state = result.get("status")
            if state in ("transientFailure", "persistentFailure", "reset"):
                raise RuntimeError(f"Knowledge indexing failed: {state}.")
            if state == "success":
                if result.get("itemsFailed", 0) or result.get("errors"):
                    raise RuntimeError("Knowledge indexing completed with failed documents.")
                return result
        time.sleep(5)
    raise TimeoutError("Knowledge indexing did not complete within 600 seconds.")


def provision(rest, settings):
    endpoint = settings["FOUNDRY_SEARCH_ENDPOINT"].rstrip("/")
    index = settings["FOUNDRY_SEARCH_INDEX_NAME"]
    source = settings["FOUNDRY_KNOWLEDGE_SOURCE_NAME"]
    kb = settings["FOUNDRY_KNOWLEDGE_BASE_NAME"]
    connection = settings["FOUNDRY_SEARCH_CONNECTION_NAME"]
    for name in (index, source, kb, connection):
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
            raise ValueError("Search object and connection names must use lowercase letters, digits, hyphens.")

    def search_url(path, version=INDEX_API_VERSION):
        return f"{endpoint}/{path}?api-version={version}"

    rest.request("PUT", search_url(f"indexes/{index}"), index_definition(index))
    rest.request("PUT", search_url(f"datasources/{index}-blob"), {
        "name": f"{index}-blob", "type": "azureblob",
        "credentials": {"connectionString": f"ResourceId={settings['AZURE_STORAGE_RESOURCE_ID']};"},
        "container": {"name": settings["KNOWLEDGE_CONTAINER"]},
    })
    status_url = search_url(f"indexers/{index}-indexer/status")
    rest.request("PUT", search_url(f"indexers/{index}-indexer"), {
        "name": f"{index}-indexer", "dataSourceName": f"{index}-blob",
        "targetIndexName": index, "schedule": {"interval": "PT5M"},
        "parameters": {"maxFailedItems": 0, "maxFailedItemsPerBatch": 0, "configuration": {
            "dataToExtract": "contentAndMetadata", "indexedFileNameExtensions": ".md",
            "parsingMode": "text",
        }},
        "fieldMappings": [
            {"sourceFieldName": "metadata_storage_path", "targetFieldName": "id",
             "mappingFunction": {"name": "base64Encode"}},
        ],
    })
    # PUT starts a new indexer's first run; wait for an idle successful run before
    # explicitly refreshing. Comparing startTime prevents accepting a stale success.
    wait_for_indexer(rest, status_url)
    previous = rest.request("GET", status_url)["lastResult"]["startTime"]
    rest.request("POST", search_url(f"indexers/{index}-indexer/run"))
    wait_for_indexer(rest, status_url, previous_start=previous)
    for attempt in range(12):
        stats = rest.request("GET", search_url(f"indexes/{index}/stats"))
        if stats.get("documentCount", 0) > 0:
            break
        if attempt == 11:
            raise RuntimeError("Knowledge index is empty; refusing to register an ungrounded agent.")
        time.sleep(5)

    rest.request("PUT", search_url(f"knowledgesources/{source}", API_VERSION), {
        "name": source, "kind": "searchIndex",
        "description": "Support policies indexed from the knowledge Blob container.",
        "searchIndexParameters": {
            "searchIndexName": index,
            "sourceDataFields": [
                {"name": "content"}, {"name": "metadata_storage_name"}, {"name": "metadata_storage_path"},
            ],
        },
    })
    rest.request("PUT", search_url(f"knowledgebases/{kb}", API_VERSION), {
        "name": kb, "description": "Ground support replies in indexed Blob policies.",
        "knowledgeSources": [{"name": source}],
        "outputMode": "extractiveData",
        "retrievalReasoningEffort": {"kind": "low"},
        "models": [{"kind": "azureOpenAI", "azureOpenAIParameters": {
            "resourceUri": settings["AZURE_OPENAI_ENDPOINT"],
            "deploymentId": settings["AZURE_OPENAI_DEPLOYMENT"],
            "modelName": settings["AZURE_OPENAI_MODEL_NAME"],
        }}],
    })
    project_id = settings["FOUNDRY_PROJECT_RESOURCE_ID"].rstrip("/")
    rest.request(
        "PUT",
        f"https://management.azure.com{project_id}/connections/{quote(connection)}?api-version=2025-10-01-preview",
        {"name": connection, "type": "Microsoft.MachineLearningServices/workspaces/connections", "properties": {
            "authType": "ProjectManagedIdentity", "category": "RemoteTool",
            "target": f"{endpoint}/knowledgebases/{kb}/mcp?api-version={API_VERSION}",
            "isSharedToAll": True, "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        }},
        scope="https://management.azure.com/.default",
    )
    result = rest.request("POST", search_url(f"knowledgebases/{kb}/retrieve", API_VERSION), {
        "messages": [{"role": "user", "content": [{"type": "text", "text": "What support policies are available?"}]}],
    })
    if not result.get("response") or not result.get("references"):
        raise RuntimeError("Foundry IQ verification returned no grounded response or source references.")
    log.info("Foundry IQ ready: %s indexed documents, knowledge base %s.", stats["documentCount"], kb)


SETTING_NAMES = (
    "FOUNDRY_SEARCH_ENDPOINT", "FOUNDRY_SEARCH_INDEX_NAME",
    "FOUNDRY_KNOWLEDGE_SOURCE_NAME", "FOUNDRY_KNOWLEDGE_BASE_NAME",
    "FOUNDRY_SEARCH_CONNECTION_NAME", "FOUNDRY_PROJECT_RESOURCE_ID",
    "AZURE_STORAGE_RESOURCE_ID", "KNOWLEDGE_CONTAINER", "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_MODEL_NAME",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-dir", type=Path, default=Path(__file__).resolve().parent.parent / "knowledge")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    settings = {name: required_setting(name) for name in SETTING_NAMES}
    if not any(path.name.lower() != "readme.md" for path in args.knowledge_dir.glob("*.md")):
        raise ValueError("Knowledge source directory must contain policy markdown files.")
    account = settings["AZURE_STORAGE_RESOURCE_ID"].rstrip("/").rsplit("/", 1)[-1]
    with DefaultAzureCredential() as credential:
        with BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=credential) as service:
            uploaded = seed_knowledge(
                BlobStore(service), settings["KNOWLEDGE_CONTAINER"], args.knowledge_dir,
            )
            log.info("Seeded %s missing policies (existing Blob knowledge is preserved).", uploaded)
        provision(AzureRest(credential), settings)


if __name__ == "__main__":
    main()
