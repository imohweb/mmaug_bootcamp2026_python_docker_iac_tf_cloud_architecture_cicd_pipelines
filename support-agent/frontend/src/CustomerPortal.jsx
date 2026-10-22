import { useCallback, useEffect, useState } from "react";
import { api, formatDate, STATUS_LABELS } from "./api.js";

const STORAGE_KEY = "mmaug-support-tickets";
const POLL_MS = 10000;

function loadSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved.filter((item) => item && item.id && item.key) : [];
  } catch {
    return [];
  }
}

function TicketCard({ ticket }) {
  return (
    <article className="card ticket" aria-label={`Ticket ${ticket.id}`}>
      <header>
        <strong>{ticket.id}</strong>
        <span className={`badge ${ticket.status}`}>{STATUS_LABELS[ticket.status] || ticket.status}</span>
      </header>
      <p className="muted">
        Assigned to {ticket.specialist} ({ticket.team}) · {formatDate(ticket.created_at)}
      </p>
      <blockquote>{ticket.message}</blockquote>
      {ticket.response ? (
        <div className="response">
          <h4>Reply from {ticket.specialist}</h4>
          <p>{ticket.response}</p>
        </div>
      ) : (
        <p className="muted">Our agent has drafted a reply. {ticket.specialist} is reviewing it now.</p>
      )}
    </article>
  );
}

export default function CustomerPortal({ config }) {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [saved, setSaved] = useState(loadSaved);
  const [tickets, setTickets] = useState({});
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [lookup, setLookup] = useState({ id: "", key: "" });

  const refresh = useCallback(async () => {
    const results = await Promise.all(
      saved.map((item) =>
        api(`/api/tickets/${encodeURIComponent(item.id)}`, { headers: { "X-Ticket-Key": item.key } })
          .then((ticket) => [item.id, ticket])
          .catch(() => [item.id, null]),
      ),
    );
    setTickets(Object.fromEntries(results.filter(([, ticket]) => ticket)));
  }, [saved]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    if (saved.length === 0) return undefined;
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [saved, refresh]);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api("/api/tickets", { method: "POST", body: form });
      setCreated(result);
      setSaved((items) => [{ id: result.ticket.id, key: result.access_key }, ...items]);
      setForm({ name: form.name, email: form.email, message: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function track(event) {
    event.preventDefault();
    setError("");
    try {
      const id = lookup.id.trim().toUpperCase();
      await api(`/api/tickets/${encodeURIComponent(id)}`, { headers: { "X-Ticket-Key": lookup.key.trim() } });
      setSaved((items) => [{ id, key: lookup.key.trim() }, ...items.filter((item) => item.id !== id)]);
      setLookup({ id: "", key: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="grid">
      <section className="card" aria-labelledby="ask-heading">
        <h2 id="ask-heading">How can we help?</h2>
        <p className="muted">
          Our AI agent triages your request, drafts an answer from our knowledge base and assigns it to the right
          specialist{config ? ` (${config.teams.map((t) => t.team).join(", ")})` : ""}. A human approves every reply.
        </p>
        <form onSubmit={submit}>
          <label htmlFor="name">Your name</label>
          <input id="name" value={form.name} onChange={update("name")} required maxLength={80} />
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={form.email} onChange={update("email")} required maxLength={254} />
          <label htmlFor="message">Your question</label>
          <textarea
            id="message"
            rows={5}
            value={form.message}
            onChange={update("message")}
            required
            minLength={10}
            maxLength={2000}
            placeholder="I was charged twice for my subscription this month."
          />
          <p className="muted small">Never include passwords, full card numbers or API keys.</p>
          <button type="submit" disabled={busy}>{busy ? "Sending…" : "Send to support"}</button>
        </form>
        {error && <p role="alert" className="error">{error}</p>}
        {created && (
          <div className="notice" role="status">
            Ticket <strong>{created.ticket.id}</strong> was assigned to {created.ticket.specialist} (
            {created.ticket.team}). Save your access key to track it from another device:{" "}
            <code>{created.access_key}</code>
          </div>
        )}
      </section>

      <section aria-labelledby="mine-heading">
        <div className="row">
          <h2 id="mine-heading">My requests</h2>
          {saved.length > 0 && <button type="button" className="ghost" onClick={refresh}>Refresh</button>}
        </div>
        {saved.length === 0 && <p className="muted">No requests yet.</p>}
        {saved.map((item) =>
          tickets[item.id] ? <TicketCard key={item.id} ticket={tickets[item.id]} /> : null,
        )}
        <form className="card compact" onSubmit={track} aria-label="Track a request">
          <h3>Track a request</h3>
          <label htmlFor="track-id">Ticket ID</label>
          <input id="track-id" value={lookup.id} required placeholder="SUP-…"
            onChange={(e) => setLookup({ ...lookup, id: e.target.value })} />
          <label htmlFor="track-key">Access key</label>
          <input id="track-key" type="password" value={lookup.key} required autoComplete="off"
            onChange={(e) => setLookup({ ...lookup, key: e.target.value })} />
          <button type="submit" className="ghost">Track</button>
        </form>
      </section>
    </div>
  );
}
