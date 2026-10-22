"""Knowledge source stored in the blob ``knowledge`` container and consumed by the agent."""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from storage import Store

log = logging.getLogger(__name__)

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "with", "this", "that",
    "have", "has", "was", "were", "can", "will", "from", "they", "them", "their",
    "what", "when", "how", "why", "who", "please", "help", "hello", "thanks", "thank",
    "our", "out", "into", "about", "after", "before", "been", "any", "all", "its",
    "need", "want", "would", "could", "should", "there", "here", "also", "just",
}


@dataclass(frozen=True)
class Section:
    document: str
    title: str
    category: str
    heading: str
    text: str


def stem(word: str) -> str:
    """Tiny suffix stripper so 'charged', 'charges' and 'charge' match."""
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> set[str]:
    return {stem(word) for word in re.findall(r"[a-z0-9]+", text.lower())
            if len(word) >= 3 and word not in STOPWORDS}


def parse_document(name: str, text: str) -> list[Section]:
    """Split a markdown document with ``---`` front matter into ``##`` sections."""
    metadata: dict[str, str] = {}
    body = text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            if value:
                metadata[key.strip().lower()] = value.strip()
        body = text[match.end():]
    title = metadata.get("title", Path(name).stem.replace("-", " ").title())
    category = metadata.get("category", "general").lower()
    sections = []
    for chunk in re.split(r"^##\s+", body, flags=re.MULTILINE)[1:]:
        heading, _, content = chunk.partition("\n")
        content = " ".join(content.split())
        if content:
            sections.append(Section(name, title, category, heading.strip(), content))
    return sections


class KnowledgeBase:
    """Loads markdown documents from storage, caches them, and ranks sections."""

    def __init__(self, store: Store, container: str, ttl_seconds: int = 300):
        self.store = store
        self.container = container
        self.ttl_seconds = ttl_seconds
        self._sections: list[Section] = []
        self._loaded_at = float("-inf")

    def sections(self) -> list[Section]:
        if time.monotonic() - self._loaded_at > self.ttl_seconds:
            loaded = []
            for name in self.store.list_names(self.container):
                if name.endswith(".md"):
                    text, _ = self.store.read(self.container, name)
                    loaded.extend(parse_document(name, text))
            self._sections = loaded
            self._loaded_at = time.monotonic()
            log.info("Loaded %s knowledge sections from %s.", len(loaded), self.container)
        return self._sections

    def documents(self) -> list[dict]:
        summary: dict[str, dict] = {}
        for section in self.sections():
            item = summary.setdefault(section.document, {
                "name": section.document, "title": section.title,
                "category": section.category, "sections": [],
            })
            item["sections"].append(section.heading)
        return list(summary.values())

    def search(self, query: str, category: str | None = None, limit: int = 3) -> list[Section]:
        terms = tokenize(query)
        scored = []
        for index, section in enumerate(self.sections()):
            overlap = len(terms & tokenize(section.text)) + 2 * len(terms & tokenize(section.heading))
            if overlap == 0:
                continue
            bonus = 1 if category and section.category == category else 0
            scored.append((overlap + bonus, -index, section))
        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [section for _, _, section in scored[:limit]]


def seed_knowledge(store: Store, container: str, source_dir: Path, overwrite: bool = False) -> int:
    """Upload ``*.md`` files from ``source_dir`` into the knowledge container."""
    existing = set(store.list_names(container))
    uploaded = 0
    for path in sorted(Path(source_dir).glob("*.md")):
        if path.name.lower() == "readme.md" or (path.name in existing and not overwrite):
            continue
        store.write(container, path.name, path.read_text(encoding="utf-8"))
        uploaded += 1
    return uploaded
