"""MMAUG customer-support agent: Flask API that also serves the React frontend."""

import logging
import os
import secrets
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import ai_client
from knowledge import KnowledgeBase, seed_knowledge
from storage import ConflictError, LocalStore, NotFoundError, Store, store_from_environment
from support_agent import SPECIALISTS, SupportAgent
from tickets import StateError, TicketService, ValidationError

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env-local", override=False)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _default_seed_dir() -> Path:
    for candidate in (HERE / "knowledge-seed", HERE.parent / "knowledge"):
        if candidate.is_dir():
            return candidate
    return HERE / "knowledge-seed"


def _default_frontend_dir() -> Path:
    for candidate in (HERE / "frontend-dist", HERE.parent / "frontend" / "dist"):
        if candidate.is_dir():
            return candidate
    return HERE / "frontend-dist"


def create_app(store: Store | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(
        MAX_CONTENT_LENGTH=16 * 1024,
        TICKETS_CONTAINER=os.getenv("TICKETS_CONTAINER", "tickets"),
        KNOWLEDGE_CONTAINER=os.getenv("KNOWLEDGE_CONTAINER", "knowledge"),
        KNOWLEDGE_SEED_DIR=Path(os.getenv("KNOWLEDGE_SEED_DIR", str(_default_seed_dir()))),
        FRONTEND_DIST=Path(os.getenv("FRONTEND_DIST", str(_default_frontend_dir()))),
    )
    state: dict = {"store": store}

    def services() -> tuple[TicketService, KnowledgeBase]:
        if "tickets" not in state:
            backing = state["store"] or store_from_environment()
            if isinstance(backing, LocalStore):
                # Offline mode only: Azure deployments read knowledge uploaded by Terraform.
                seeded = seed_knowledge(backing, app.config["KNOWLEDGE_CONTAINER"],
                                        app.config["KNOWLEDGE_SEED_DIR"])
                if seeded:
                    app.logger.info("Seeded %s local knowledge documents.", seeded)
            knowledge = KnowledgeBase(backing, app.config["KNOWLEDGE_CONTAINER"])
            state["knowledge"] = knowledge
            state["tickets"] = TicketService(backing, app.config["TICKETS_CONTAINER"],
                                             SupportAgent(knowledge))
        return state["tickets"], state["knowledge"]

    def specialist_only(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            token = os.getenv("SPECIALIST_API_TOKEN", "")
            if len(token) < 32 or token.startswith("REPLACE-"):
                app.logger.warning("Specialist console disabled: set a random SPECIALIST_API_TOKEN.")
                return jsonify(error="The specialist console is not configured."), 503
            supplied = request.headers.get("Authorization", "")
            if not secrets.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
                app.logger.warning("Unauthorized specialist request.")
                return jsonify(error="A valid specialist bearer token is required."), 401
            return view(*args, **kwargs)
        return wrapper

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'none'",
        )
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/api/config")
    def config():
        try:
            mode = ai_client.ai_mode()
        except ValueError:
            mode = "misconfigured"
        return jsonify(
            service="MMAUG Customer Support Agent",
            ai_mode=mode,
            teams=[{"category": s.category, "team": s.team, "specialist": s.name}
                   for s in SPECIALISTS.values()],
        )

    @app.post("/api/tickets")
    def create_ticket():
        tickets, _ = services()
        try:
            ticket, access_key = tickets.create(request.get_json(silent=True))
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        app.logger.info("Created ticket %s for %s.", ticket["id"], ticket["team"])
        return jsonify(ticket=ticket, access_key=access_key), 201

    @app.get("/api/tickets/<ticket_id>")
    def customer_ticket(ticket_id: str):
        tickets, _ = services()
        try:
            return jsonify(tickets.get_for_customer(ticket_id, request.headers.get("X-Ticket-Key", "")))
        except NotFoundError:
            return jsonify(error="Ticket not found. Check the ticket ID and access key."), 404

    @app.get("/api/specialist/tickets")
    @specialist_only
    def list_tickets():
        tickets, _ = services()
        try:
            items = tickets.list(request.args.get("status") or None, request.args.get("category") or None)
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        return jsonify(tickets=items)

    @app.get("/api/specialist/tickets/<ticket_id>")
    @specialist_only
    def specialist_ticket(ticket_id: str):
        tickets, _ = services()
        try:
            return jsonify(tickets.get(ticket_id))
        except NotFoundError:
            return jsonify(error="Ticket not found."), 404

    @app.post("/api/specialist/tickets/<ticket_id>/<action>")
    @specialist_only
    def update_ticket(ticket_id: str, action: str):
        tickets, _ = services()
        handlers = {"approve": tickets.approve, "reassign": tickets.reassign}
        if action not in handlers:
            return jsonify(error="Use approve or reassign."), 404
        try:
            ticket = handlers[action](ticket_id, request.get_json(silent=True))
        except ValidationError as error:
            return jsonify(error=str(error)), 400
        except NotFoundError:
            return jsonify(error="Ticket not found."), 404
        except (StateError, ConflictError) as error:
            message = str(error) if isinstance(error, StateError) else "The ticket changed; reload and retry."
            return jsonify(error=message), 409
        app.logger.info("Ticket %s: %s.", ticket_id, action)
        return jsonify(ticket)

    @app.get("/api/specialist/knowledge")
    @specialist_only
    def knowledge_documents():
        _, knowledge = services()
        return jsonify(container=app.config["KNOWLEDGE_CONTAINER"], documents=knowledge.documents())

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str):
        if path.startswith("api/") or path == "api":
            return jsonify(error="Route not found."), 404
        dist = app.config["FRONTEND_DIST"]
        if not (dist / "index.html").is_file():
            return jsonify(message="MMAUG Customer Support Agent API. Build the React frontend "
                                   "(npm run build) to serve the web UI."), 200
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Route not found."), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(413)
    def too_large(_error):
        app.logger.warning("Request exceeded the 16 KiB limit.")
        return jsonify(error="Request body must not exceed 16 KiB."), 413

    @app.errorhandler(500)
    def server_error(_error):
        return jsonify(error="Unexpected server error; check the application logs."), 500

    return app


app = create_app()


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
