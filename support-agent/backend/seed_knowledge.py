"""Upload the markdown knowledge source to the configured store (Azure Blob or local).

Terraform uploads the knowledge files in Azure; use this script for Azurite, a
local folder, or to re-sync documents manually: python seed_knowledge.py --overwrite
"""

import argparse
import os
from pathlib import Path

from knowledge import seed_knowledge
from storage import store_from_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(Path(__file__).resolve().parent.parent / "knowledge"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    container = os.getenv("KNOWLEDGE_CONTAINER", "knowledge")
    count = seed_knowledge(store_from_environment(), container, Path(args.source), args.overwrite)
    print(f"Uploaded {count} knowledge document(s) to container '{container}'.")


if __name__ == "__main__":
    main()
