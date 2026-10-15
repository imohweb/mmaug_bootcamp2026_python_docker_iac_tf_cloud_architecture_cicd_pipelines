"""Terraform's data-plane bridge for a dedicated, lab-owned prompt agent."""

import argparse
import logging
import os
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential


def reconcile(project: AIProjectClient, action: str) -> None:
    name = os.environ["FOUNDRY_AGENT_NAME"]
    if action == "delete":
        try:
            project.agents.delete(agent_name=name)
        except ResourceNotFoundError:
            logging.info("Agent %s is already absent.", name)
        else:
            logging.info("Deleted agent %s.", name)
        return

    model = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    instructions = os.environ["FOUNDRY_AGENT_INSTRUCTIONS"]
    try:
        existing = project.agents.get(agent_name=name).versions.latest
    except ResourceNotFoundError:
        existing = None
    if existing is not None:
        definition = existing.definition
        if (
            isinstance(definition, PromptAgentDefinition)
            and definition.model == model
            and definition.instructions == instructions
        ):
            logging.info("Agent %s version %s already matches.", name, existing.version)
            return
        raise RuntimeError(
            f"Agent {name} already exists with a different definition. "
            "Choose a unique lab agent name; do not overwrite an unmanaged agent."
        )
    agent = project.agents.create_version(
        agent_name=name,
        definition=PromptAgentDefinition(model=model, instructions=instructions),
    )
    logging.info("Created agent %s version %s.", agent.name, agent.version)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "delete"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    with DefaultAzureCredential() as credential:
        with AIProjectClient(
            endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            credential=credential,
        ) as project:
            for attempt in range(12):
                try:
                    reconcile(project, args.action)
                    break
                except HttpResponseError as error:
                    if error.status_code != 403 or attempt == 11:
                        raise
                    logging.warning(
                        "Foundry denied access (403). Waiting 10s for RBAC propagation "
                        "(attempt %s/12); persistent denial fails the Terraform operation.",
                        attempt + 1,
                    )
                    time.sleep(10)


if __name__ == "__main__":
    main()
