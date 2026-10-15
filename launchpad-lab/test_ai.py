import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from azure.ai.projects.models import PromptAgentDefinition
from azure.core.exceptions import ResourceNotFoundError
from openai import OpenAIError

from ai_demo import ask_agent, ask_model
from app import app
from manage_agent import reconcile


TOKEN = "a" * 40
SETTINGS = {
    "AI_DEMO_API_TOKEN": TOKEN,
    "AZURE_OPENAI_ENDPOINT": "https://demo.openai.azure.com/",
    "AZURE_OPENAI_DEPLOYMENT": "demo-model",
    "AZURE_OPENAI_API_KEY": "",
    "FOUNDRY_PROJECT_ENDPOINT": "https://demo.services.ai.azure.com/api/projects/launchpad",
    "FOUNDRY_AGENT_NAME": "mmaug-launchpad-tutor",
    "FOUNDRY_AGENT_INSTRUCTIONS": "Teach beginners.",
}


class AiRouteTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, SETTINGS, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = app.test_client()

    def post(self, mode="model", **kwargs):
        kwargs.setdefault("headers", {"Authorization": f"Bearer {TOKEN}"})
        kwargs.setdefault("json", {"prompt": "Explain containers."})
        return self.client.post(f"/ai/{mode}", **kwargs)

    @patch("app.ask_model", return_value="A packaged runtime.")
    @patch("app.ask_agent", return_value="An agent uses instructions and a model.")
    def test_both_modes(self, agent, model):
        for mode, expected in (
            ("model", "A packaged runtime."),
            ("agent", "An agent uses instructions and a model."),
        ):
            response = self.post(mode)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"mode": mode, "answer": expected})
        model.assert_called_once_with("Explain containers.")
        agent.assert_called_once_with("Explain containers.")

    @patch("app.ask_model")
    def test_authentication_required_before_sdk_call(self, model):
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            self.assertEqual(self.post(headers=headers).status_code, 401)
        model.assert_not_called()

    def test_unconfigured_token_disables_ai(self):
        for value in ("", "short", "REPLACE-WITH-A-RANDOM-DEMO-TOKEN"):
            with self.subTest(value=value), patch.dict(os.environ, {"AI_DEMO_API_TOKEN": value}):
                self.assertEqual(self.post().status_code, 503)

    @patch("app.ask_model", return_value="Answer")
    def test_prompt_validation(self, model):
        for payload in ({}, [], None, {"prompt": 3}, {"prompt": " "}, {"prompt": "a" * 2001}):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/ai/model", json=payload,
                    headers={"Authorization": f"Bearer {TOKEN}"},
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.post(json={"prompt": "a" * 2000}).status_code, 200)
        model.assert_called_once()

    @patch("app.ask_model", return_value="OK")
    def test_trims_prompt(self, model):
        self.assertEqual(self.post(json={"prompt": "  hello  "}).status_code, 200)
        model.assert_called_once_with("hello")

    def test_bad_json_and_large_body(self):
        headers = {"Authorization": f"Bearer {TOKEN}"}
        response = self.client.post(
            "/ai/model", data="{", content_type="application/json", headers=headers
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/ai/model", data="a" * 16385, content_type="application/json", headers=headers
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json)

    def test_unknown_mode(self):
        self.assertEqual(self.post("unknown").status_code, 404)

    @patch("app.ask_model")
    def test_errors_are_explicit_and_sanitized(self, model):
        for error, status in (
            (ValueError("missing endpoint"), 503),
            (OpenAIError("upstream details"), 502),
            (RuntimeError("empty answer"), 502),
        ):
            with self.subTest(error=error):
                model.side_effect = error
                response = self.post()
                self.assertEqual(response.status_code, status)
                self.assertNotIn(str(error), response.get_data(as_text=True))


class SdkTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, SETTINGS, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    @patch("ai_demo.AzureOpenAI")
    @patch("ai_demo.get_bearer_token_provider")
    @patch("ai_demo.DefaultAzureCredential")
    def test_direct_model_uses_entra_and_deployment(self, credential, token_provider, factory):
        client = factory.return_value.__enter__.return_value
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Answer"))]
        )
        self.assertEqual(ask_model("Question"), "Answer")
        factory.assert_called_once_with(
            azure_endpoint=SETTINGS["AZURE_OPENAI_ENDPOINT"],
            api_version="2024-10-21", timeout=20, max_retries=0,
            api_key=None, azure_ad_token_provider=token_provider.return_value,
        )
        token_provider.assert_called_once_with(
            credential.return_value.__enter__.return_value,
            "https://cognitiveservices.azure.com/.default",
        )
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "demo-model")
        self.assertEqual(client.chat.completions.create.call_args.kwargs["max_completion_tokens"], 300)

    @patch("ai_demo.AzureOpenAI")
    @patch("ai_demo.DefaultAzureCredential")
    def test_optional_api_key_and_empty_model_reply(self, credential, factory):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "local-test-only"}):
            client = factory.return_value.__enter__.return_value
            client.chat.completions.create.return_value = SimpleNamespace(choices=[])
            with self.assertRaises(RuntimeError):
                ask_model("Question")
        credential.assert_not_called()
        self.assertEqual(factory.call_args.kwargs["api_key"], "local-test-only")

    @patch("ai_demo.AIProjectClient")
    @patch("ai_demo.DefaultAzureCredential")
    def test_agent_is_invoked_not_created_per_request(self, credential, factory):
        project = factory.return_value.__enter__.return_value
        client = project.get_openai_client.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text="Agent answer"
        )
        self.assertEqual(ask_agent("Question"), "Agent answer")
        project.get_openai_client.assert_called_once_with(
            agent_name="mmaug-launchpad-tutor", timeout=20, max_retries=0
        )
        client.responses.create.assert_called_once_with(input="Question", max_output_tokens=300)
        project.agents.create_version.assert_not_called()
        client.responses.create.return_value.status = "failed"
        with self.assertRaises(RuntimeError):
            ask_agent("Question")

    def test_missing_or_placeholder_settings_fail_before_network(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": ""}):
            with self.assertRaises(ValueError):
                ask_model("Question")
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
        self.assertEqual(definition.instructions, "Teach beginners.")

    def test_matching_agent_is_not_duplicated(self):
        self.project.agents.get.return_value.versions.latest.definition = PromptAgentDefinition(
            model="demo-model", instructions="Teach beginners."
        )
        reconcile(self.project, "create")
        self.project.agents.create_version.assert_not_called()

    def test_conflicting_agent_is_not_overwritten(self):
        self.project.agents.get.return_value.versions.latest.definition = PromptAgentDefinition(
            model="different-model", instructions="Other agent."
        )
        with self.assertRaises(RuntimeError):
            reconcile(self.project, "create")
        self.project.agents.create_version.assert_not_called()

    def test_delete_and_already_absent(self):
        reconcile(self.project, "delete")
        self.project.agents.delete.assert_called_once_with(agent_name="mmaug-launchpad-tutor")
        self.project.agents.delete.side_effect = ResourceNotFoundError("Not found")
        reconcile(self.project, "delete")


if __name__ == "__main__":
    unittest.main()
