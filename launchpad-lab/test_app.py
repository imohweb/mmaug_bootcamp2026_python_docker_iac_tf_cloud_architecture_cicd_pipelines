import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from werkzeug.serving import make_server

from app import app, main, summarize


class SummaryTests(unittest.TestCase):
    def test_total_and_average(self):
        self.assertEqual(summarize([5, 10, 15]), {"total": 30, "average": 10.0})

    def test_negative_and_zero(self):
        self.assertEqual(summarize([-3, 0, 3]), {"total": 0, "average": 0.0})

    def test_wrong_count(self):
        for values in ([], [1], [1, 2], [1, 2, 3, 4]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                summarize(values)

    def test_invalid_port(self):
        for port in ("abc", "0", "65536"):
            with self.subTest(port=port), patch.dict(os.environ, {"PORT": port}):
                with self.assertRaises(ValueError):
                    main()


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0, app, threaded=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path):
        try:
            response = urlopen(self.base_url + path, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.headers["Content-Type"], "application/json")
            return response.status, json.load(response)

    def test_health(self):
        self.assertEqual(self.request("/health"), (200, {"status": "ok"}))

    def test_configured_message(self):
        with patch.dict(os.environ, {"APP_MESSAGE": "Hello from a test!"}):
            self.assertEqual(self.request("/"), (200, {"message": "Hello from a test!"}))

    def test_valid_sum(self):
        self.assertEqual(
            self.request("/sum?values=5,10,15"),
            (200, {"total": 30, "average": 10.0}),
        )

    def test_bad_input(self):
        for query in ("", "?values=", "?values=a,2,3", "?values=1,2",
                      "?values=1,2,3,4", "?values=1,2,3&values=4,5,6"):
            with self.subTest(query=query):
                status, payload = self.request("/sum" + query)
                self.assertEqual(status, 400)
                self.assertIn("error", payload)

    def test_missing_route(self):
        self.assertEqual(self.request("/missing"), (404, {"error": "Route not found."}))

    def test_home_page(self):
        with urlopen(self.base_url + "/ui", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
            page = response.read()
            self.assertIn(b"<title>MMAUG Bootcamp 2026 Sessions Launchpad by Imoh Etuk</title>", page)
            self.assertIn(b"covers the October 17 and 27, 2026 sessions", page)
            self.assertIn(b"Microsoft Foundry agent and Azure OpenAI model integration", page)
            self.assertIn(b"private bearer token", page)
            self.assertIn(b"No production user authentication or database", page)
            self.assertNotIn(b"no authentication, database, or AI model", page)

    def test_oversized_input(self):
        status, payload = self.request("/sum?values=" + "1" * 121)
        self.assertEqual(status, 400)
        self.assertIn("120 characters", payload["error"])


if __name__ == "__main__":
    unittest.main()
