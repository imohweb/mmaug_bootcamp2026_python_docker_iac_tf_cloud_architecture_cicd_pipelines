import os
from contextlib import ExitStack

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


def required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "YOUR-" in value or value.startswith("REPLACE-"):
        raise ValueError(f"Configure {name} before running the AI demo.")
    return value


def ask_model(prompt: str) -> str:
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
            timeout=20,
            max_retries=0,
            api_key=api_key or None,
            azure_ad_token_provider=token_provider,
        ))
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "Explain cloud concepts to beginners concisely."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=300,
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
                agent_name=agent_name, timeout=20, max_retries=0
            ) as client:
                response = client.responses.create(input=prompt, max_output_tokens=300)
                if response.status != "completed" or not response.output_text:
                    raise RuntimeError("The agent response did not complete with text.")
                return response.output_text
