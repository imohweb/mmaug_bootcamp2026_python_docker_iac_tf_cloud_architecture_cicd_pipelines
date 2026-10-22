import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError

from knowledge import KnowledgeBase, parse_document, seed_knowledge
from storage import BlobStore, ConflictError, LocalStore, NotFoundError, store_from_environment
from support_agent import SupportAgent, _parse_ai_reply, classify

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"


class ClassifierTests(unittest.TestCase):
    def test_routes_to_specialist_categories(self):
        cases = {
            "I was charged twice and need a refund": ("billing", "normal"),
            "The mobile app crashes with an error": ("technical", "normal"),
            "I forgot my password and my account is locked": ("account", "normal"),
            "What are your opening hours?": ("general", "normal"),
            "URGENT: my account was hacked": ("account", "high"),
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(classify(message), expected)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = LocalStore(folder.name)
        seed_knowledge(self.store, "knowledge", KNOWLEDGE)
        self.knowledge = KnowledgeBase(self.store, "knowledge")

    def test_parse_front_matter_and_sections(self):
        sections = parse_document("x.md", "---\ntitle: Demo\ncategory: billing\n---\n# Demo\n"
                                          "## Refunds\nRefund text.\n\n## Empty\n")
        self.assertEqual(len(sections), 1)
        self.assertEqual((sections[0].title, sections[0].category, sections[0].heading),
                         ("Demo", "billing", "Refunds"))

    def test_search_ranks_relevant_sections(self):
        top = self.knowledge.search("How do I reset my password?", "account")[0]
        self.assertEqual((top.document, top.heading), ("account-and-security.md", "Password reset"))
        top = self.knowledge.search("I was charged twice for my invoice, can I get a refund?", "billing")[0]
        self.assertEqual(top.heading, "Duplicate or unexpected charges")
        self.assertEqual(self.knowledge.search("zzzz qqqq"), [])

    def test_seed_does_not_overwrite_without_flag(self):
        self.store.write("knowledge", "general-information.md", "custom")
        self.assertEqual(seed_knowledge(self.store, "knowledge", KNOWLEDGE), 0)
        self.assertEqual(self.store.read("knowledge", "general-information.md")[0], "custom")
        self.assertEqual(seed_knowledge(self.store, "knowledge", KNOWLEDGE, overwrite=True), 4)

    def test_cache_reloads_after_ttl(self):
        self.knowledge.ttl_seconds = 0
        count = len(self.knowledge.sections())
        self.store.write("knowledge", "extra.md", "## New\nFresh content.")
        self.assertEqual(len(self.knowledge.sections()), count + 1)


class DraftTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        store = LocalStore(folder.name)
        seed_knowledge(store, "knowledge", KNOWLEDGE)
        self.agent = SupportAgent(KnowledgeBase(store, "knowledge"))

    def test_template_draft_without_ai(self):
        with patch.dict(os.environ, {"AI_MODE": "off"}):
            draft = self.agent.draft("Ko Ko", "I need a refund for my annual plan")
        self.assertEqual((draft.category, draft.source), ("billing", "knowledge-template"))
        self.assertIn("Hello Ko Ko", draft.text)
        self.assertIn("Aye Chan", draft.text)

    @patch("support_agent.ai_client.complete")
    def test_ai_draft_can_refine_category(self, complete):
        complete.return_value = ("agent", '```json\n{"category": "account", "priority": "high", '
                                          '"reply": "Please use Forgot password."}\n```')
        draft = self.agent.draft("Ko Ko", "I need a refund for my annual plan")
        self.assertEqual((draft.category, draft.priority, draft.source), ("account", "high", "ai-agent"))
        self.assertEqual(draft.text, "Please use Forgot password.")
        system, prompt = complete.call_args.args
        self.assertIn("JSON", system)
        self.assertIn("Refund policy", prompt)

    @patch("support_agent.ai_client.complete")
    def test_ai_failures_fall_back_to_template(self, complete):
        for effect in (RuntimeError("down"), ValueError("config"), None):
            with self.subTest(effect=effect):
                complete.side_effect = effect
                complete.return_value = ("model", "not json")
                draft = self.agent.draft("Ko Ko", "Refund please for the invoice")
                self.assertEqual(draft.source, "knowledge-template")

    def test_parse_ai_reply_validation(self):
        self.assertIsNone(_parse_ai_reply("[]"))
        self.assertIsNone(_parse_ai_reply('{"reply": ""}'))
        parsed = _parse_ai_reply('{"category": "sales", "priority": "low", "reply": "Hi"}')
        self.assertEqual(parsed, {"category": None, "priority": None, "reply": "Hi", "sources": []})

    @patch.dict(os.environ, {"AI_MODE": "agent"})
    @patch("support_agent.ai_client.complete")
    def test_iq_agent_gets_question_not_keyword_excerpts(self, complete):
        complete.return_value = ("agent", '{"category": "billing", "priority": "normal", '
                                 '"reply": "A specialist will review the charge.", '
                                 '"sources": [{"document": "billing.md", "heading": "Charges"}]}')
        draft = self.agent.draft("Ko Ko", "Why was I charged twice?")
        system, prompt = complete.call_args.args
        self.assertIn("knowledge base tool", system)
        self.assertIn("charged twice", prompt)
        self.assertNotIn("Knowledge excerpts:", prompt)
        self.assertNotIn("Duplicate or unexpected charges", prompt)
        self.assertEqual(draft.sources, [{"document": "billing.md", "heading": "Charges"}])

    def test_source_validation_ignores_malformed_entries(self):
        parsed = _parse_ai_reply('{"reply":"Hi", "sources":[null, {"document":2}, '
                                 '{"document":"policy.md","heading":"Policy"}]}')
        self.assertEqual(parsed["sources"], [{"document": "policy.md", "heading": "Policy"}])


class StorageTests(unittest.TestCase):
    def test_local_store_etag_and_create_only(self):
        with tempfile.TemporaryDirectory() as folder:
            store = LocalStore(folder)
            etag = store.write("tickets", "a.json", "1", create_only=True)
            with self.assertRaises(ConflictError):
                store.write("tickets", "a.json", "2", create_only=True)
            store.write("tickets", "a.json", "2", etag=etag)
            with self.assertRaises(ConflictError):
                store.write("tickets", "a.json", "3", etag=etag)
            with self.assertRaises(NotFoundError):
                store.read("tickets", "missing.json")
            with self.assertRaises(ValueError):
                store.read("tickets", "../escape")
            self.assertEqual(store.list_names("tickets"), ["a.json"])
            self.assertEqual(store.list_names("empty"), [])

    def test_blob_store_maps_azure_errors(self):
        service = MagicMock()
        blob = service.get_blob_client.return_value
        store = BlobStore(service)
        blob.download_blob.return_value.readall.return_value = b"hello"
        blob.download_blob.return_value.properties.etag = '"0x1"'
        self.assertEqual(store.read("tickets", "a.json"), ("hello", '"0x1"'))
        blob.upload_blob.return_value = {"etag": '"0x2"'}
        self.assertEqual(store.write("tickets", "a.json", "x", etag='"0x1"'), '"0x2"')
        self.assertEqual(blob.upload_blob.call_args.kwargs["etag"], '"0x1"')
        store.write("tickets", "b.json", "x", create_only=True)
        self.assertFalse(blob.upload_blob.call_args.kwargs["overwrite"])
        for error in (ResourceExistsError("exists"), ResourceModifiedError("changed")):
            blob.upload_blob.side_effect = error
            with self.assertRaises(ConflictError):
                store.write("tickets", "a.json", "x")
        blob.download_blob.side_effect = ResourceNotFoundError("missing")
        with self.assertRaises(NotFoundError):
            store.read("tickets", "a.json")
        listed = MagicMock()
        listed.name = "a.json"
        service.get_container_client.return_value.list_blobs.return_value = [listed]
        self.assertEqual(store.list_names("tickets"), ["a.json"])

    def test_store_selection_from_environment(self):
        with patch.dict(os.environ, {"STORAGE_ACCOUNT_URL": "", "AZURE_STORAGE_CONNECTION_STRING": "",
                                     "DATA_DIR": "/tmp/support-data"}):
            self.assertIsInstance(store_from_environment(), LocalStore)
        with patch.dict(os.environ, {"STORAGE_ACCOUNT_URL": "https://evil.example.com"}):
            with self.assertRaises(ValueError):
                store_from_environment()
        with patch.dict(os.environ, {"STORAGE_ACCOUNT_URL": "https://mmaugdata.blob.core.windows.net/"}):
            with patch("storage.BlobStore.from_settings") as factory:
                store_from_environment()
        factory.assert_called_once_with("https://mmaugdata.blob.core.windows.net/", "")


if __name__ == "__main__":
    unittest.main()
