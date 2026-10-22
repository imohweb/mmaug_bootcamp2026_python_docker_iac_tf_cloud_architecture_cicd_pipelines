import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from setup_knowledge_index import AzureRest, index_definition, provision, wait_for_indexer


SETTINGS = {
    "FOUNDRY_SEARCH_ENDPOINT": "https://support.search.windows.net",
    "FOUNDRY_SEARCH_INDEX_NAME": "support-policies",
    "FOUNDRY_KNOWLEDGE_SOURCE_NAME": "support-source",
    "FOUNDRY_KNOWLEDGE_BASE_NAME": "support-kb",
    "FOUNDRY_SEARCH_CONNECTION_NAME": "support-iq",
    "FOUNDRY_PROJECT_RESOURCE_ID": "/subscriptions/sub/resourceGroups/rg/providers/"
                                   "Microsoft.CognitiveServices/accounts/foundry/projects/support",
    "AZURE_STORAGE_RESOURCE_ID": "/subscriptions/sub/resourceGroups/rg/providers/"
                                 "Microsoft.Storage/storageAccounts/supportdata",
    "KNOWLEDGE_CONTAINER": "knowledge",
    "AZURE_OPENAI_ENDPOINT": "https://foundry.openai.azure.com/",
    "AZURE_OPENAI_DEPLOYMENT": "support-model",
    "AZURE_OPENAI_MODEL_NAME": "gpt-6.1-sol",
}


class KnowledgeIndexTests(unittest.TestCase):
    @patch("setup_knowledge_index.wait_for_indexer")
    def test_provisions_real_iq_and_managed_identity_connection(self, wait):
        rest = MagicMock()
        rest.request.side_effect = lambda method, url, *args, **kwargs: (
            {"lastResult": {"startTime": "old"}} if "/status?" in url else
            {"documentCount": 4} if "/stats?" in url else
            {"response": [{"role": "assistant"}], "references": [{"id": "0"}]}
            if "/retrieve?" in url else {}
        )
        provision(rest, SETTINGS)
        calls = rest.request.call_args_list
        bodies = {call.args[1].split("?")[0]: call.args[2] for call in calls if len(call.args) > 2}
        root = SETTINGS["FOUNDRY_SEARCH_ENDPOINT"]
        source = bodies[f"{root}/knowledgesources/support-source"]
        self.assertEqual(source["kind"], "searchIndex")
        self.assertEqual(source["searchIndexParameters"]["searchIndexName"], "support-policies")
        kb = bodies[f"{root}/knowledgebases/support-kb"]
        self.assertEqual(kb["knowledgeSources"], [{"name": "support-source"}])
        self.assertEqual(kb["models"][0]["azureOpenAIParameters"]["deploymentId"], "support-model")
        self.assertEqual(kb["models"][0]["azureOpenAIParameters"]["modelName"], "gpt-6.1-sol")
        datasource = bodies[f"{root}/datasources/support-policies-blob"]
        self.assertEqual(datasource["credentials"]["connectionString"],
                         f"ResourceId={SETTINGS['AZURE_STORAGE_RESOURCE_ID']};")
        self.assertNotIn("AccountKey", json.dumps(bodies))
        connection = next(body for url, body in bodies.items() if "/connections/" in url)
        self.assertEqual(connection["properties"]["authType"], "ProjectManagedIdentity")
        self.assertEqual(connection["properties"]["audience"], "https://search.azure.com/")
        self.assertIn("/knowledgebases/support-kb/mcp?api-version=2026-08-01-preview",
                      connection["properties"]["target"])
        self.assertEqual(wait.call_count, 2)
        self.assertEqual(wait.call_args.kwargs["previous_start"], "old")

    @patch("setup_knowledge_index.time.sleep")
    @patch("setup_knowledge_index.wait_for_indexer")
    def test_empty_index_stops_before_knowledge_base(self, wait, sleep):
        rest = MagicMock()
        rest.request.return_value = {"lastResult": {"startTime": "old"}, "documentCount": 0}
        with self.assertRaisesRegex(RuntimeError, "index is empty"):
            provision(rest, SETTINGS)
        self.assertFalse(any("/knowledgebases/" in call.args[1] for call in rest.request.call_args_list))

    @patch("setup_knowledge_index.wait_for_indexer")
    def test_ungrounded_smoke_test_is_failure(self, wait):
        rest = MagicMock()
        rest.request.return_value = {"lastResult": {"startTime": "old"}, "documentCount": 4}
        with self.assertRaisesRegex(RuntimeError, "no grounded"):
            provision(rest, SETTINGS)

    def test_index_is_semantically_configured_and_content_retrievable(self):
        index = index_definition("support")
        self.assertEqual(index["semantic"]["defaultConfiguration"], "support-semantic")
        content = next(field for field in index["fields"] if field["name"] == "content")
        self.assertTrue(content["searchable"])
        self.assertTrue(content["retrievable"])

    @patch("setup_knowledge_index.time.sleep")
    def test_wait_does_not_accept_stale_success(self, sleep):
        rest = MagicMock()
        rest.request.side_effect = [
            {"lastResult": {"status": "success", "startTime": "old"}},
            {"lastResult": {"status": "inProgress", "startTime": "new"}},
            {"lastResult": {"status": "success", "startTime": "new", "itemsFailed": 0}},
        ]
        self.assertEqual(wait_for_indexer(rest, "https://example/status", previous_start="old")["startTime"], "new")
        self.assertEqual(sleep.call_count, 2)

    def test_wait_rejects_partial_and_persistent_failures(self):
        for result in (
            {"status": "persistentFailure", "startTime": "new"},
            {"status": "success", "startTime": "new", "itemsFailed": 1},
            {"status": "success", "startTime": "new", "errors": [{"message": "Failure"}]},
        ):
            rest = MagicMock()
            rest.request.return_value = {"lastResult": result}
            with self.subTest(result=result), self.assertRaises(RuntimeError):
                wait_for_indexer(rest, "https://example/status")

    @patch("setup_knowledge_index.time.monotonic", side_effect=[0, 601])
    def test_wait_timeout(self, clock):
        with self.assertRaises(TimeoutError):
            wait_for_indexer(MagicMock(), "https://example/status")

    @patch("setup_knowledge_index.urlopen")
    def test_rest_uses_bearer_token_for_correct_audience(self, open_url):
        credential = MagicMock()
        credential.get_token.return_value = SimpleNamespace(token="test-token")
        open_url.return_value.__enter__.return_value.read.return_value = b'{"ok":true}'
        self.assertEqual(AzureRest(credential).request("PUT", "https://example", {"x": 1}), {"ok": True})
        credential.get_token.assert_called_once_with("https://search.azure.com/.default")
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(json.loads(request.data), {"x": 1})

    @patch("setup_knowledge_index.time.sleep")
    @patch("setup_knowledge_index.urlopen")
    def test_rest_retries_propagating_rbac_but_not_invalid_api(self, open_url, sleep):
        credential = MagicMock()
        credential.get_token.return_value = SimpleNamespace(token="test-token")
        open_url.side_effect = HTTPError("https://example", 403, "denied", {}, None)
        with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
            AzureRest(credential).request("GET", "https://example")
        self.assertEqual(open_url.call_count, 12)
        open_url.reset_mock()
        open_url.side_effect = HTTPError("https://example", 400, "bad API", {}, None)
        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            AzureRest(credential).request("GET", "https://example")
        self.assertEqual(open_url.call_count, 1)

    @patch("setup_knowledge_index.time.sleep")
    @patch("setup_knowledge_index.urlopen")
    def test_explicit_refresh_retries_when_scheduled_indexer_is_running(self, open_url, sleep):
        credential = MagicMock()
        credential.get_token.return_value = SimpleNamespace(token="test-token")
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b""
        open_url.side_effect = [HTTPError("https://example", 409, "busy", {}, None), response]
        self.assertEqual(AzureRest(credential).request(
            "POST", "https://example/indexers/support/run?api-version=2024-07-01"
        ), {})
        self.assertEqual(open_url.call_count, 2)
        sleep.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
