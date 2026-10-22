"""Customer-support agent: triage, specialist routing and knowledge-grounded drafting."""

import json
import logging
import re
from dataclasses import asdict, dataclass

import ai_client
from knowledge import KnowledgeBase, Section

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Specialist:
    id: str
    name: str
    team: str
    category: str


# Teaching roster: one human specialist per support category.
SPECIALISTS = {
    "billing": Specialist("aye-chan", "Aye Chan", "Billing & Payments", "billing"),
    "technical": Specialist("min-thu", "Min Thu", "Technical Support", "technical"),
    "account": Specialist("su-mon", "Su Mon", "Account & Security", "account"),
    "general": Specialist("kyaw-zin", "Kyaw Zin", "General Enquiries", "general"),
}

KEYWORDS = {
    "billing": {"invoice", "refund", "charge", "charged", "payment", "card", "bill", "billing",
                "receipt", "credit", "subscription", "renewal", "pay", "paid", "price", "cost"},
    "technical": {"error", "crash", "bug", "slow", "loading", "load", "api", "app",
                  "integration", "timeout", "broken", "working", "e500", "e503", "mobile", "429"},
    "account": {"password", "login", "log", "sign", "locked", "lock", "mfa", "2fa", "authenticator",
                "security", "reset", "close", "delete", "export", "privacy", "hacked", "email"},
}
URGENT = {"urgent", "asap", "immediately", "outage", "down", "fraud", "hacked", "stolen", "breach"}

SYSTEM_PROMPT = (
    "You are the MMAUG customer-support agent. Draft a reply that a human specialist will "
    "review before it reaches the customer. Use only the knowledge excerpts provided; if they "
    "do not answer the question, say a specialist will follow up. Never promise refunds, "
    "never ask for passwords, full card numbers or API keys, and keep replies under 180 words. "
    'Respond with JSON only: {"category": "billing|technical|account|general", '
    '"priority": "normal|high", "reply": "<draft reply>"}.'
)


@dataclass
class Draft:
    category: str
    priority: str
    text: str
    source: str
    sources: list[dict]


def _word_forms(message: str) -> set[str]:
    forms = set()
    for word in re.findall(r"[a-z0-9]+", message.lower()):
        forms.add(word)
        for suffix in ("es", "s", "ing", "ed"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                forms.add(word[: -len(suffix)])
    return forms


def classify(message: str) -> tuple[str, str]:
    words = _word_forms(message)
    scores = {category: len(words & terms) for category, terms in KEYWORDS.items()}
    best = max(scores, key=lambda category: scores[category])
    category = best if scores[best] > 0 else "general"
    priority = "high" if words & URGENT else "normal"
    return category, priority


def _knowledge_prompt(name: str, message: str, sections: list[Section]) -> str:
    excerpts = "\n\n".join(
        f"[{index}] {section.title} > {section.heading}\n{section.text}"
        for index, section in enumerate(sections, start=1)
    ) or "(no matching knowledge)"
    return f"Customer name: {name}\nCustomer message:\n{message}\n\nKnowledge excerpts:\n{excerpts}"


def _parse_ai_reply(text: str) -> dict | None:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    reply = data.get("reply")
    if not isinstance(reply, str) or not 1 <= len(reply.strip()) <= 4000:
        return None
    return {
        "category": data.get("category") if data.get("category") in SPECIALISTS else None,
        "priority": data.get("priority") if data.get("priority") in ("normal", "high") else None,
        "reply": reply.strip(),
        "sources": [
            {"document": item["document"][:2048], "heading": item["heading"][:300]}
            for item in data.get("sources", [])
            if isinstance(item, dict)
            and isinstance(item.get("document"), str)
            and isinstance(item.get("heading"), str)
        ][:10] if isinstance(data.get("sources", []), list) else [],
    }


def template_reply(name: str, specialist: Specialist, sections: list[Section]) -> str:
    if sections:
        guidance = f"Here is what our {sections[0].title.lower()} guide says about " \
                   f"\"{sections[0].heading}\":\n\n{sections[0].text}"
    else:
        guidance = "A specialist is reviewing your message and will reply with the next steps."
    return (
        f"Hello {name},\n\nThank you for contacting MMAUG Support. {guidance}\n\n"
        f"If this does not resolve your request, simply reply with more details.\n\n"
        f"Kind regards,\n{specialist.name}\n{specialist.team}"
    )


class SupportAgent:
    def __init__(self, knowledge: KnowledgeBase):
        self.knowledge = knowledge

    def draft(self, name: str, message: str) -> Draft:
        category, priority = classify(message)
        sections = self.knowledge.search(message, category)
        sources = [{"document": s.document, "heading": s.heading} for s in sections]
        source = "knowledge-template"
        reply = None
        try:
            if ai_client.ai_mode() == "agent":
                system = SYSTEM_PROMPT.replace(
                    "Use only the knowledge excerpts provided;",
                    "Call the knowledge base tool and use only its retrieved knowledge;",
                )
                prompt = f"Customer name: {name}\nCustomer message:\n{message}"
            else:
                system = SYSTEM_PROMPT
                prompt = _knowledge_prompt(name, message, sections)
            result = ai_client.complete(system, prompt)
        except Exception:  # Any AI failure falls back; a human still approves every reply.
            log.exception("AI drafting failed; using the knowledge template instead.")
            result = None
        if result is not None:
            mode, text = result
            parsed = _parse_ai_reply(text)
            if parsed is None:
                log.warning("AI reply was not valid JSON; using the knowledge template instead.")
            else:
                category = parsed["category"] or category
                priority = parsed["priority"] or priority
                reply = parsed["reply"]
                source = f"ai-{mode}"
                if mode == "agent":
                    sources = parsed["sources"]
        specialist = SPECIALISTS[category]
        if reply is None:
            reply = template_reply(name, specialist, sections)
        return Draft(
            category=category,
            priority=priority,
            text=reply,
            source=source,
            sources=sources,
        )


def specialist_dict(category: str) -> dict:
    return asdict(SPECIALISTS[category])
