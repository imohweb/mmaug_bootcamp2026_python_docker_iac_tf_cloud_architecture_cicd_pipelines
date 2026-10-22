"""Ticket lifecycle: customer request -> agent draft -> specialist approval -> customer reply."""

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone

from storage import ConflictError, NotFoundError, Store
from support_agent import SPECIALISTS, SupportAgent, specialist_dict

AWAITING = "awaiting_approval"
RESPONDED = "responded"
STATUSES = (AWAITING, RESPONDED)
TICKET_ID = re.compile(r"^SUP-[0-9A-F]{10}$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[A-Za-z]{2,24}$")
LIST_LIMIT = 100


class ValidationError(ValueError):
    """Client input is invalid; the message is safe to return to the caller."""


class StateError(Exception):
    """The ticket is not in a state that allows the requested action."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _text(value, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValidationError(f"{field} must be {minimum}-{maximum} characters.")
    return value.strip()


def customer_view(ticket: dict) -> dict:
    specialist = ticket["assigned_to"]
    return {
        "id": ticket["id"],
        "status": ticket["status"],
        "created_at": ticket["created_at"],
        "updated_at": ticket["updated_at"],
        "message": ticket["message"],
        "team": specialist["team"],
        "specialist": specialist["name"],
        "response": ticket["response"] if ticket["status"] == RESPONDED else None,
    }


def specialist_view(ticket: dict) -> dict:
    return {key: value for key, value in ticket.items() if key != "access_key_sha256"}


class TicketService:
    def __init__(self, store: Store, container: str, agent: SupportAgent):
        self.store = store
        self.container = container
        self.agent = agent

    def _load(self, ticket_id: str) -> tuple[dict, str]:
        if not TICKET_ID.fullmatch(ticket_id):
            raise NotFoundError(ticket_id)
        text, etag = self.store.read(self.container, f"{ticket_id}.json")
        return json.loads(text), etag

    def _save(self, ticket: dict, *, etag: str | None = None, create_only: bool = False) -> None:
        self.store.write(
            self.container, f"{ticket['id']}.json", json.dumps(ticket, indent=2),
            etag=etag, create_only=create_only,
        )

    def create(self, payload) -> tuple[dict, str]:
        if not isinstance(payload, dict):
            raise ValidationError("Send a JSON object with name, email and message.")
        name = _text(payload.get("name"), "Name", 1, 80)
        email = _text(payload.get("email"), "Email", 6, 254)
        if not EMAIL.fullmatch(email):
            raise ValidationError("Enter a valid email address.")
        message = _text(payload.get("message"), "Message", 10, 2000)

        draft = self.agent.draft(name, message)
        access_key = secrets.token_urlsafe(24)
        created = _now()
        ticket = {
            "id": "",
            "created_at": created,
            "updated_at": created,
            "status": AWAITING,
            "customer": {"name": name, "email": email},
            "message": message,
            "category": draft.category,
            "priority": draft.priority,
            "assigned_to": specialist_dict(draft.category),
            "draft": {"text": draft.text, "source": draft.source, "sources": draft.sources},
            "response": None,
            "approved_by": None,
            "approved_at": None,
            "history": [{"at": created, "event": "created",
                         "detail": f"Agent assigned {draft.category} ({draft.source})."}],
            "access_key_sha256": _hash_key(access_key),
        }
        for _ in range(5):
            ticket["id"] = f"SUP-{secrets.token_hex(5).upper()}"
            try:
                self._save(ticket, create_only=True)
                return customer_view(ticket), access_key
            except ConflictError:
                continue
        raise RuntimeError("Could not allocate a unique ticket ID.")

    def get_for_customer(self, ticket_id: str, access_key: str) -> dict:
        ticket, _ = self._load(ticket_id)
        if not secrets.compare_digest(_hash_key(access_key or ""), ticket["access_key_sha256"]):
            raise NotFoundError(ticket_id)
        return customer_view(ticket)

    def get(self, ticket_id: str) -> dict:
        return specialist_view(self._load(ticket_id)[0])

    def list(self, status: str | None = None, category: str | None = None) -> list[dict]:
        if status and status not in STATUSES:
            raise ValidationError(f"status must be one of {', '.join(STATUSES)}.")
        if category and category not in SPECIALISTS:
            raise ValidationError(f"category must be one of {', '.join(SPECIALISTS)}.")
        tickets = []
        for name in self.store.list_names(self.container):
            if not name.endswith(".json"):
                continue
            try:
                ticket = json.loads(self.store.read(self.container, name)[0])
            except (NotFoundError, json.JSONDecodeError):
                continue
            if (status is None or ticket["status"] == status) and (
                category is None or ticket["category"] == category
            ):
                tickets.append(specialist_view(ticket))
        tickets.sort(key=lambda item: item["created_at"], reverse=True)
        return tickets[:LIST_LIMIT]

    def approve(self, ticket_id: str, payload) -> dict:
        if not isinstance(payload, dict):
            raise ValidationError("Send a JSON object with the approved response.")
        response = _text(payload.get("response"), "Response", 1, 4000)
        ticket, etag = self._load(ticket_id)
        if ticket["status"] != AWAITING:
            raise StateError("Only tickets awaiting approval can be approved.")
        edited = response != ticket["draft"]["text"]
        now = _now()
        ticket.update(status=RESPONDED, response=response, updated_at=now,
                      approved_by=ticket["assigned_to"]["name"], approved_at=now)
        ticket["history"].append({
            "at": now, "event": "approved",
            "detail": f"{ticket['approved_by']} {'edited and ' if edited else ''}approved the reply.",
        })
        self._save(ticket, etag=etag)
        return specialist_view(ticket)

    def reassign(self, ticket_id: str, payload) -> dict:
        category = payload.get("category") if isinstance(payload, dict) else None
        if category not in SPECIALISTS:
            raise ValidationError(f"category must be one of {', '.join(SPECIALISTS)}.")
        ticket, etag = self._load(ticket_id)
        if ticket["status"] != AWAITING:
            raise StateError("Only tickets awaiting approval can be reassigned.")
        if category == ticket["category"]:
            raise ValidationError("The ticket is already assigned to that team.")
        previous = ticket["assigned_to"]["name"]
        now = _now()
        ticket.update(category=category, assigned_to=specialist_dict(category), updated_at=now)
        ticket["history"].append({
            "at": now, "event": "reassigned",
            "detail": f"{previous} reassigned the ticket to {ticket['assigned_to']['team']}.",
        })
        self._save(ticket, etag=etag)
        return specialist_view(ticket)
