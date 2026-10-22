import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createFrontendServer } from "./server.mjs";

let backend, frontend, base;
const listen = (server) => new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const close = (server) => new Promise((resolve, reject) => {
  server.closeAllConnections();
  server.close((error) => error ? reject(error) : resolve());
});

before(async () => {
  backend = http.createServer((req, res) => {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ method: req.method, path: req.url, auth: req.headers.authorization }));
  });
  await listen(backend);
  frontend = createFrontendServer(`http://127.0.0.1:${backend.address().port}`);
  await listen(frontend);
  base = `http://127.0.0.1:${frontend.address().port}`;
});
after(async () => { await close(frontend); await close(backend); });

test("serves React and security headers", async () => {
  const response = await fetch(base);
  assert.equal(response.status, 200);
  assert.match(await response.text(), /id="root"/);
  assert.equal(response.headers.get("x-frame-options"), "DENY");
});
test("proxies specialist authentication and query without changing paths", async () => {
  const response = await fetch(base + "/api/specialist/tickets?category=billing", {
    headers: { Authorization: "Bearer synthetic-test-token" },
  });
  assert.deepEqual(await response.json(), {
    method: "GET", path: "/api/specialist/tickets?category=billing",
    auth: "Bearer synthetic-test-token",
  });
});
test("proxies health and POST requests", async () => {
  assert.equal((await (await fetch(base + "/health")).json()).path, "/health");
  const response = await fetch(base + "/api/tickets", {
    method: "POST", body: JSON.stringify({ message: "Test" }),
  });
  assert.equal((await response.json()).method, "POST");
});
test("rejects unsafe backend origins", () => {
  for (const origin of ["http://example.com", "https://user:password@example.com", "https://example.com/api"]) {
    assert.throws(() => createFrontendServer(origin));
  }
});
test("returns explicit 502 when backend cannot connect", async () => {
  const temporary = http.createServer();
  await listen(temporary);
  const port = temporary.address().port;
  await close(temporary);
  const proxy = createFrontendServer(`http://127.0.0.1:${port}`);
  await listen(proxy);
  try {
    const response = await fetch(`http://127.0.0.1:${proxy.address().port}/api/config`);
    assert.equal(response.status, 502);
    assert.equal((await response.json()).error, "Backend unavailable.");
  } finally { await close(proxy); }
});
