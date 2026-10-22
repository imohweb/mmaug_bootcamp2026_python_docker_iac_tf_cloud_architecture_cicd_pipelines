import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app, main
from storage import LocalStore

TOKEN = "s" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}
KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"


class SupportApiTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = LocalStore(folder.name)
        environment = patch.dict(os.environ, {"SPECIALIST_API_TOKEN": TOKEN, "AI_MODE": "off"})
        environment.start()
        self.addCleanup(environment.stop)
        self.app = create_app(self.store)
        self.app.config.update(KNOWLEDGE_SEED_DIR=KNOWLEDGE, FRONTEND_DIST=Path(folder.name) / "dist")
        self.client = self.app.test_client()

    def submit(self, message="I was charged twice for my invoice this month.", **extra):
        payload = {"name": "Thandar", "email": "thandar@example.com", "message": message, **extra}
        return self.client.post("/api/tickets", json=payload)

    def test_health_and_config(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})
        config = self.client.get("/api/config").json
        self.assertEqual(config["ai_mode"], "off")
        self.assertEqual({team["category"] for team in config["teams"]},
                         {"billing", "technical", "account", "general"})

    def test_full_approval_workflow(self):
        created = self.submit()
        self.assertEqual(created.status_code, 201)
        ticket, key = created.json["ticket"], created.json["access_key"]
        self.assertEqual(ticket["status"], "awaiting_approval")
        self.assertEqual(ticket["team"], "Billing & Payments")
        self.assertIsNone(ticket["response"])
        self.assertNotIn("draft", ticket)

        queue = self.client.get("/api/specialist/tickets?status=awaiting_approval", headers=AUTH).json
        self.assertEqual([item["id"] for item in queue["tickets"]], [ticket["id"]])
        detail = queue["tickets"][0]
        self.assertNotIn("access_key_sha256", detail)
        self.assertEqual(detail["draft"]["source"], "knowledge-template")
        self.assertTrue(detail["draft"]["sources"])
        self.assertIn("billing-and-payments.md", {s["document"] for s in detail["draft"]["sources"]})

        approved = self.client.post(f"/api/specialist/tickets/{ticket['id']}/approve",
                                    json={"response": "We refunded the duplicate."}, headers=AUTH)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json["approved_by"], "Aye Chan")
        self.assertIn("edited and approved", approved.json["history"][-1]["detail"])

        seen = self.client.get(f"/api/tickets/{ticket['id']}", headers={"X-Ticket-Key": key})
        self.assertEqual(seen.json["status"], "responded")
        self.assertEqual(seen.json["response"], "We refunded the duplicate.")

        again = self.client.post(f"/api/specialist/tickets/{ticket['id']}/approve",
                                 json={"response": "Twice"}, headers=AUTH)
        self.assertEqual(again.status_code, 409)

    def test_reassign_routes_to_another_specialist(self):
        ticket = self.submit("My mobile app crashes with error E503 after login.").json["ticket"]
        self.assertEqual(ticket["team"], "Technical Support")
        url = f"/api/specialist/tickets/{ticket['id']}/reassign"
        moved = self.client.post(url, json={"category": "account"}, headers=AUTH)
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.json["assigned_to"]["name"], "Su Mon")
        self.assertEqual(self.client.post(url, json={"category": "account"}, headers=AUTH).status_code, 400)
        self.assertEqual(self.client.post(url, json={"category": "sales"}, headers=AUTH).status_code, 400)
        filtered = self.client.get("/api/specialist/tickets?category=account", headers=AUTH).json
        self.assertEqual(len(filtered["tickets"]), 1)

    def test_customer_needs_matching_access_key(self):
        ticket = self.submit().json["ticket"]
        for headers in ({}, {"X-Ticket-Key": "wrong"}):
            response = self.client.get(f"/api/tickets/{ticket['id']}", headers=headers)
            self.assertEqual(response.status_code, 404)
        for ticket_id in ("SUP-0000000000", "../secret", "sup-abc"):
            self.assertEqual(self.client.get(f"/api/tickets/{ticket_id}",
                                             headers={"X-Ticket-Key": "x"}).status_code, 404)

    def test_input_validation(self):
        for payload in (None, [], {}, {"name": "A", "email": "bad", "message": "long enough text"},
                        {"name": "", "email": "a@b.co", "message": "long enough text"},
                        {"name": "A", "email": "a@b.co", "message": "short"},
                        {"name": "A", "email": "a@b.co", "message": "x" * 2001}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/tickets", json=payload).status_code, 400)
        self.assertEqual(self.client.post("/api/tickets", data="{", content_type="application/json").status_code, 400)
        large = self.client.post("/api/tickets", data="a" * 16385, content_type="application/json")
        self.assertEqual(large.status_code, 413)

    def test_specialist_auth(self):
        self.assertEqual(self.client.get("/api/specialist/tickets").status_code, 401)
        self.assertEqual(self.client.get("/api/specialist/tickets",
                                         headers={"Authorization": "Bearer wrong"}).status_code, 401)
        for value in ("", "short", "REPLACE-" + "x" * 40):
            with self.subTest(value=value), patch.dict(os.environ, {"SPECIALIST_API_TOKEN": value}):
                self.assertEqual(self.client.get("/api/specialist/tickets", headers=AUTH).status_code, 503)

    def test_specialist_errors(self):
        self.assertEqual(self.client.get("/api/specialist/tickets?status=nope", headers=AUTH).status_code, 400)
        self.assertEqual(self.client.get("/api/specialist/tickets/SUP-0000000000", headers=AUTH).status_code, 404)
        ticket = self.submit().json["ticket"]
        base = f"/api/specialist/tickets/{ticket['id']}"
        self.assertEqual(self.client.post(f"{base}/delete", headers=AUTH).status_code, 404)
        self.assertEqual(self.client.post(f"{base}/approve", json={"response": " "}, headers=AUTH).status_code, 400)
        self.assertEqual(self.client.get(base, headers=AUTH).json["id"], ticket["id"])

    def test_knowledge_is_read_from_store(self):
        response = self.client.get("/api/specialist/knowledge", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        names = {doc["name"] for doc in response.json["documents"]}
        self.assertEqual(names, {path.name for path in KNOWLEDGE.glob("*.md") if path.name != "README.md"})
        self.assertEqual(set(self.store.list_names("knowledge")), names)

    def test_frontend_serving(self):
        self.assertIn("Build the React frontend", self.client.get("/").json["message"])
        dist = self.app.config["FRONTEND_DIST"]
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<div id=root></div>")
        (dist / "assets" / "app.js").write_text("console.log(1)")
        for path, expected in (("/specialist", b"root"), ("/assets/app.js", b"console.log(1)"), ("/", b"root")):
            with self.client.get(path) as response:
                self.assertIn(expected, response.data)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.client.get("/api/missing").status_code, 404)

    def test_invalid_port(self):
        for port in ("abc", "0", "65536"):
            with self.subTest(port=port), patch.dict(os.environ, {"PORT": port}):
                with self.assertRaises(ValueError):
                    main()


class RealHttpTests(unittest.TestCase):
    """Exercise the WSGI app through a real socket, as Gunicorn would."""

    def test_health_over_http(self):
        import json
        from urllib.request import urlopen

        from werkzeug.serving import make_server

        with tempfile.TemporaryDirectory() as folder:
            server = make_server("127.0.0.1", 0, create_app(LocalStore(folder)), threaded=True)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/health", timeout=3) as response:
                    self.assertEqual(response.headers["Content-Type"], "application/json")
                    self.assertEqual(json.load(response), {"status": "ok"})
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
