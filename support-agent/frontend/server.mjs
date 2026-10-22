import http from "node:http";
import https from "node:https";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

export function createFrontendServer(origin, dist = new URL("./dist/", import.meta.url)) {
  const backend = new URL(origin);
  if (!["https:", "http:"].includes(backend.protocol) ||
      backend.username || backend.password || backend.search || backend.hash ||
      backend.pathname !== "/" ||
      (backend.protocol === "http:" && !["backend", "127.0.0.1", "localhost"].includes(backend.hostname))) {
    throw new Error("BACKEND_ORIGIN must be an HTTPS origin (HTTP allowed only for local backend).");
  }
  const root = path.resolve(fileURLToPath(dist));
  return http.createServer(async (req, res) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");
    res.setHeader("X-Frame-Options", "DENY");
    res.setHeader("Content-Security-Policy",
      "default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'none'");
    const requestUrl = new URL(req.url, "http://localhost");
    const pathname = requestUrl.pathname;
    if (pathname === "/api" || pathname.startsWith("/api/") || pathname === "/health") {
      const transport = backend.protocol === "https:" ? https : http;
      const headers = { ...req.headers, host: backend.host };
      delete headers.connection;
      const target = new URL(backend);
      target.pathname = pathname;
      target.search = requestUrl.search;
      const upstream = transport.request(target, {
        method: req.method, headers, timeout: 110000,
      }, (response) => {
        const responseHeaders = { ...response.headers };
        delete responseHeaders.connection;
        res.writeHead(response.statusCode, responseHeaders);
        response.pipe(res);
      });
      upstream.on("timeout", () => upstream.destroy(new Error("Backend request timed out")));
      upstream.on("error", (error) => {
        console.error("Backend proxy failed:", error.message);
        if (res.headersSent) res.destroy();
        else {
          res.writeHead(502, { "Content-Type": "application/json", "Cache-Control": "no-store" });
          res.end(JSON.stringify({ error: "Backend unavailable." }));
        }
      });
      req.on("aborted", () => upstream.destroy());
      req.pipe(upstream);
      return;
    }
    if (!["GET", "HEAD"].includes(req.method)) {
      res.writeHead(405, { Allow: "GET, HEAD" });
      res.end();
      return;
    }
    try {
      const requested = path.resolve(root, "." + decodeURIComponent(pathname));
      if (requested !== root && !requested.startsWith(root + path.sep)) {
        res.writeHead(400);
        res.end("Invalid path");
        return;
      }
      let file = requested;
      try {
        if (!(await stat(file)).isFile()) file = path.join(root, "index.html");
      } catch (error) {
        if (error.code !== "ENOENT" && error.code !== "ENOTDIR") throw error;
        file = path.join(root, "index.html");
      }
      const info = await stat(file);
      res.writeHead(200, {
        "Content-Type": types[path.extname(file)] || "application/octet-stream",
        "Content-Length": info.size,
        "Cache-Control": "no-cache",
      });
      if (req.method === "HEAD") res.end();
      else createReadStream(file).on("error", (error) => {
        console.error("Static file read failed:", error.message);
        res.destroy();
      }).pipe(res);
    } catch (error) {
      console.error("Frontend request failed:", error.message);
      res.writeHead(error instanceof URIError ? 400 : 500);
      res.end("Unable to serve request");
    }
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.env.BACKEND_ORIGIN) throw new Error("BACKEND_ORIGIN is required.");
  const port = Number(process.env.PORT || "8000");
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("Invalid PORT.");
  createFrontendServer(process.env.BACKEND_ORIGIN).listen(port, "0.0.0.0", () => {
    console.log(`Frontend listening on port ${port}`);
  });
}
