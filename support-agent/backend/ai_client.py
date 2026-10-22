"""Optional Microsoft Foundry / Azure OpenAI calls used to draft support replies."""

import os
from contextlib import ExitStack

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

AI_MODES = ("off", "model", "agent")


def required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "YOUR-" in value or value.startswith("REPLACE-"):
        raise ValueError(f"Configure {name} before enabling AI drafting.")
    return value


def ai_mode() -> str:
    mode = os.getenv("AI_MODE", "off").strip().lower() or "off"
    if mode not in AI_MODES:
        raise ValueError(f"AI_MODE must be one of {', '.join(AI_MODES)}.")
    return mode


def ask_model(system: str, prompt: str) -> str:
    endpoint = required_setting("AZURE_OPENAI_ENDPOINT")
    deployment = required_setting("AZURE_OPENAI_DEPLOYMENT")
    with ExitStack() as stack:
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        token_provider = None
        if not api_key:
            credential = stack.enter_context(DefaultAzureCredential())
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
        client = stack.enter_context(AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            timeout=30,
            max_retries=0,
            api_key=api_key or None,
            azure_ad_token_provider=token_provider,
        ))
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=700,
        )
        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise RuntimeError("The model returned no text; inspect content filters and response status.")
        return text


def ask_agent(prompt: str) -> str:
    endpoint = required_setting("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = required_setting("FOUNDRY_AGENT_NAME")
    with DefaultAzureCredential() as credential:
        with AIProjectClient(endpoint=endpoint, credential=credential) as project:
            with project.get_openai_client(
                agent_name=agent_name, timeout=90, max_retries=0
            ) as client:
                response = client.responses.create(input=prompt, max_output_tokens=1800)
                if response.status != "completed" or not response.output_text:
                    raise RuntimeError("The agent response did not complete with text.")
                if os.getenv("FOUNDRY_SEARCH_ENDPOINT", "").strip():
                    retrieved = any(
                        getattr(item, "type", None) == "mcp_call"
                        and getattr(item, "server_label", None) == "support-knowledge"
                        and getattr(item, "name", None) == "knowledge_base_retrieve"
                        and getattr(item, "error", None) is None
                        and getattr(item, "status", None) in (None, "completed")
                        and bool(getattr(item, "output", None))
                        for item in response.output
                    )
                    if not retrieved:
                        raise RuntimeError("The agent did not successfully retrieve Foundry IQ knowledge.")
                return response.output_text


def complete(system: str, prompt: str) -> tuple[str, str] | None:
    """Return ``(mode, text)`` from the configured AI service, or ``None`` when AI is off."""
    mode = ai_mode()
    if mode == "off":
        return None
    if mode == "model":
        return mode, ask_model(system, prompt)
    # The Foundry agent already carries the support instructions; include them for clarity.
    return mode, ask_agent(f"{system}\n\n{prompt}")
