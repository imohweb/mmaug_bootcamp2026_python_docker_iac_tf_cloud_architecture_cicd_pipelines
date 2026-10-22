import { useCallback, useEffect, useState } from "react";
import { api, formatDate, STATUS_LABELS } from "./api.js";

export default function SpecialistConsole({ config }) {
  const [tokenInput, setTokenInput] = useState("");
  const [token, setToken] = useState("");
  const [filters, setFilters] = useState({ status: "awaiting_approval", category: "" });
  const [queue, setQueue] = useState([]);
  const [selected, setSelected] = useState(null);
  const [reply, setReply] = useState("");
  const [reassignTo, setReassignTo] = useState("");
  const [knowledge, setKnowledge] = useState([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const auth = { Authorization: `Bearer ${token}` };

  const load = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
      const [list, docs] = await Promise.all([
        api(`/api/specialist/tickets?${query}`, { headers: { Authorization: `Bearer ${token}` } }),
        api("/api/specialist/knowledge", { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setQueue(list.tickets);
      setKnowledge(docs.documents);
    } catch (err) {
      setError(err.message);
      if (err.status === 401) setToken("");
    }
  }, [token, filters]);

  useEffect(() => {
    load();
  }, [load]);

  function open(ticket) {
    setSelected(ticket);
    setReply(ticket.response || ticket.draft.text);
    setReassignTo("");
    setMessage("");
  }

  async function act(action, body) {
    setError("");
    try {
      const ticket = await api(`/api/specialist/tickets/${selected.id}/${action}`, {
        method: "POST",
        body,
        headers: auth,
      });
      open(ticket);
      setMessage(action === "approve" ? "Reply approved and delivered to the customer." : `Reassigned to ${ticket.assigned_to.team}.`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!token) {
    return (
      <section className="card narrow" aria-labelledby="signin-heading">
        <h2 id="signin-heading">Specialist sign-in</h2>
        <p className="muted">Enter the specialist token configured for this environment. It is kept in memory only.</p>
        <form onSubmit={(e) => { e.preventDefault(); setToken(tokenInput.trim()); setTokenInput(""); }}>
          <label htmlFor="specialist-token">Specialist token</label>
          <input id="specialist-token" type="password" autoComplete="off" required minLength={32}
            value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} />
          <button type="submit">Open console</button>
        </form>
        {error && <p role="alert" className="error">{error}</p>}
      </section>
    );
  }

  return (
    <div className="console">
      <aside className="card">
        <div className="row">
          <h2>Queue</h2>
          <button type="button" className="ghost" onClick={load}>Refresh</button>
        </div>
        <label htmlFor="status-filter">Status</label>
        <select id="status-filter" value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="awaiting_approval">Awaiting approval</option>
          <option value="responded">Responded</option>
          <option value="">All</option>
        </select>
        <label htmlFor="team-filter">Team</label>
        <select id="team-filter" value={filters.category}
          onChange={(e) => setFilters({ ...filters, category: e.target.value })}>
          <option value="">All teams</option>
          {config?.teams.map((t) => <option key={t.category} value={t.category}>{t.team} — {t.specialist}</option>)}
        </select>
        <ul className="queue">
          {queue.length === 0 && <li className="muted">No tickets.</li>}
          {queue.map((ticket) => (
            <li key={ticket.id}>
              <button type="button" className={selected?.id === ticket.id ? "item active" : "item"} onClick={() => open(ticket)}>
                <span>{ticket.id}{ticket.priority === "high" && <span className="badge high">high</span>}</span>
                <span className="muted small">{ticket.assigned_to.name} · {ticket.customer.name}</span>
              </button>
            </li>
          ))}
        </ul>
        <h3>Knowledge (Blob Storage)</h3>
        <ul className="muted small">
          {knowledge.map((doc) => <li key={doc.name}>{doc.title} ({doc.sections.length} sections)</li>)}
        </ul>
      </aside>

      <section className="card" aria-live="polite">
        {error && <p role="alert" className="error">{error}</p>}
        {message && <p role="status" className="notice">{message}</p>}
        {!selected ? (
          <p className="muted">Select a ticket to review the agent's draft.</p>
        ) : (
          <>
            <div className="row">
              <h2>{selected.id}</h2>
              <span className={`badge ${selected.status}`}>{STATUS_LABELS[selected.status]}</span>
            </div>
            <p className="muted">
              {selected.customer.name} &lt;{selected.customer.email}&gt; · {formatDate(selected.created_at)} ·
              priority {selected.priority} · assigned to {selected.assigned_to.name} ({selected.assigned_to.team})
            </p>
            <blockquote>{selected.message}</blockquote>
            <p className="muted small">
              Draft source: <strong>{selected.draft.source}</strong>
              {selected.draft.sources.length > 0 && <> · knowledge: {selected.draft.sources.map((s) => `${s.document} › ${s.heading}`).join("; ")}</>}
            </p>
            <label htmlFor="reply">Reply to customer</label>
            <textarea id="reply" rows={10} maxLength={4000} value={reply}
              readOnly={selected.status !== "awaiting_approval"} onChange={(e) => setReply(e.target.value)} />
            {selected.status === "awaiting_approval" && (
              <div className="actions">
                <button type="button" onClick={() => act("approve", { response: reply })}>Approve &amp; send</button>
                <select aria-label="Reassign to team" value={reassignTo} onChange={(e) => setReassignTo(e.target.value)}>
                  <option value="">Reassign to…</option>
                  {config?.teams.filter((t) => t.category !== selected.category).map((t) => (
                    <option key={t.category} value={t.category}>{t.team}</option>
                  ))}
                </select>
                <button type="button" className="ghost" disabled={!reassignTo}
                  onClick={() => act("reassign", { category: reassignTo })}>Reassign</button>
              </div>
            )}
            <h3>History</h3>
            <ol className="history small">
              {selected.history.map((entry) => <li key={`${entry.at}-${entry.event}`}>{formatDate(entry.at)} — {entry.detail}</li>)}
            </ol>
          </>
        )}
      </section>
    </div>
  );
}
