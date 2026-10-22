import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from azure.ai.projects.models import PromptAgentDefinition
from azure.core.exceptions import ResourceNotFoundError

from ai_client import ai_mode, ask_agent, ask_model, complete
from manage_agent import agent_definition, reconcile

SETTINGS = {
    "AI_MODE": "model",
    "AZURE_OPENAI_ENDPOINT": "https://demo.openai.azure.com/",
    "AZURE_OPENAI_DEPLOYMENT": "demo-model",
    "AZURE_OPENAI_API_KEY": "",
    "FOUNDRY_PROJECT_ENDPOINT": "https://demo.services.ai.azure.com/api/projects/launchpad",
    "FOUNDRY_AGENT_NAME": "mmaug-support-agent",
    "FOUNDRY_AGENT_INSTRUCTIONS": "Draft support replies.",
}


class SdkTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, SETTINGS, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    @patch("ai_client.AzureOpenAI")
    @patch("ai_client.get_bearer_token_provider")
    @patch("ai_client.DefaultAzureCredential")
    def test_direct_model_uses_entra_and_deployment(self, credential, token_provider, factory):
        client = factory.return_value.__enter__.return_value
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Answer"))]
        )
        self.assertEqual(ask_model("System", "Question"), "Answer")
        factory.assert_called_once_with(
            azure_endpoint=SETTINGS["AZURE_OPENAI_ENDPOINT"],
            api_version="2024-10-21", timeout=30, max_retries=0,
            api_key=None, azure_ad_token_provider=token_provider.return_value,
        )
        token_provider.assert_called_once_with(
            credential.return_value.__enter__.return_value,
            "https://cognitiveservices.azure.com/.default",
        )
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "demo-model")
        self.assertEqual(kwargs["messages"][0], {"role": "system", "content": "System"})

    @patch("ai_client.AzureOpenAI")
    @patch("ai_client.DefaultAzureCredential")
    def test_optional_api_key_and_empty_model_reply(self, credential, factory):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "local-test-only"}):
            client = factory.return_value.__enter__.return_value
            client.chat.completions.create.return_value = SimpleNamespace(choices=[])
            with self.assertRaises(RuntimeError):
                ask_model("System", "Question")
        credential.assert_not_called()
        self.assertEqual(factory.call_args.kwargs["api_key"], "local-test-only")

    @patch("ai_client.AIProjectClient")
    @patch("ai_client.DefaultAzureCredential")
    def test_agent_is_invoked_not_created_per_request(self, credential, factory):
        project = factory.return_value.__enter__.return_value
        client = project.get_openai_client.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text="Agent answer"
        )
        self.assertEqual(ask_agent("Question"), "Agent answer")
        project.get_openai_client.assert_called_once_with(
            agent_name="mmaug-support-agent", timeout=90, max_retries=0
        )
        project.agents.create_version.assert_not_called()
        client.responses.create.return_value.status = "failed"
        with self.assertRaises(RuntimeError):
            ask_agent("Question")

    @patch("ai_client.AIProjectClient")
    @patch("ai_client.DefaultAzureCredential")
    def test_iq_agent_requires_successful_retrieval(self, credential, factory):
        client = factory.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        response = SimpleNamespace(status="completed", output_text="Grounded answer", output=[])
        client.responses.create.return_value = response
        with patch.dict(os.environ, {"FOUNDRY_SEARCH_ENDPOINT": "https://support.search.windows.net"}):
            with self.assertRaisesRegex(RuntimeError, "successfully retrieve"):
                ask_agent("Question")
            call = SimpleNamespace(
                type="mcp_call", server_label="support-knowledge", name="knowledge_base_retrieve",
                error=None, status="completed", output='{"references": [{"id": "1"}]}',
            )
            response.output = [call]
            self.assertEqual(ask_agent("Question"), "Grounded answer")
            call.error = {"message": "Access denied"}
            with self.assertRaises(RuntimeError):
                ask_agent("Question")

    @patch("ai_client.ask_agent", return_value="A")
    @patch("ai_client.ask_model", return_value="M")
    def test_complete_dispatches_by_mode(self, model, agent):
        for mode, expected in (("off", None), ("model", ("model", "M")), ("agent", ("agent", "A"))):
            with self.subTest(mode=mode), patch.dict(os.environ, {"AI_MODE": mode}):
                self.assertEqual(complete("S", "P"), expected)
        model.assert_called_once_with("S", "P")
        self.assertIn("S", agent.call_args.args[0])
        with patch.dict(os.environ, {"AI_MODE": "magic"}), self.assertRaises(ValueError):
            ai_mode()

    def test_missing_or_placeholder_settings_fail_before_network(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": ""}):
            with self.assertRaises(ValueError):
                ask_model("S", "Question")
        with patch.dict(os.environ, {"FOUNDRY_PROJECT_ENDPOINT": "https://YOUR-NAME.example"}):
            with self.assertRaises(ValueError):
                ask_agent("Question")


class AgentLifecycleTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, SETTINGS, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.project = MagicMock()

    def test_create_missing_agent(self):
        self.project.agents.get.side_effect = ResourceNotFoundError("Not found")
        reconcile(self.project, "create")
        definition = self.project.agents.create_version.call_args.kwargs["definition"]
        self.assertIsInstance(definition, PromptAgentDefinition)
        self.assertEqual(definition.model, "demo-model")
        self.assertEqual(definition.instructions, "Draft support replies.")

    def test_matching_agent_is_not_duplicated(self):
        self.project.agents.get.return_value.versions.latest.definition = PromptAgentDefinition(
            model="demo-model", instructions="Draft support replies."
        )
        reconcile(self.project, "create")
        self.project.agents.create_version.assert_not_called()

    def test_iq_tool_uses_project_identity_connection(self):
        with patch.dict(os.environ, {
            "FOUNDRY_SEARCH_ENDPOINT": "https://support.search.windows.net/",
            "FOUNDRY_KNOWLEDGE_BASE_NAME": "support-kb",
            "FOUNDRY_SEARCH_CONNECTION_NAME": "support-iq",
        }):
            definition = agent_definition()
            tool = definition.tools[0].as_dict()
            self.assertEqual(tool["type"], "mcp")
            self.assertEqual(tool["allowed_tools"], ["knowledge_base_retrieve"])
            self.assertEqual(tool["project_connection_id"], "support-iq")
            self.assertEqual(tool["server_url"],
                             "https://support.search.windows.net/knowledgebases/support-kb/mcp"
                             "?api-version=2026-08-01-preview")
            self.assertIn("call knowledge_base_retrieve", definition.instructions)
            self.project.agents.get.return_value.versions.latest.definition = definition
            reconcile(self.project, "create")
            self.project.agents.create_version.assert_not_called()
            self.project.agents.get.return_value.versions.latest.definition = PromptAgentDefinition(
                model=definition.model, instructions=definition.instructions, tools=[]
            )
            with self.assertRaises(RuntimeError):
                reconcile(self.project, "create")

    def test_conflicting_agent_is_not_overwritten(self):
        self.project.agents.get.return_value.versions.latest.definition = PromptAgentDefinition(
            model="different-model", instructions="Other agent."
        )
        with self.assertRaises(RuntimeError):
            reconcile(self.project, "create")
        self.project.agents.create_version.assert_not_called()

    def test_delete_and_already_absent(self):
        reconcile(self.project, "delete")
        self.project.agents.delete.assert_called_once_with(agent_name="mmaug-support-agent")
        self.project.agents.delete.side_effect = ResourceNotFoundError("Not found")
        reconcile(self.project, "delete")


if __name__ == "__main__":
    unittest.main()
