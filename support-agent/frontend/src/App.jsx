import { useEffect, useState } from "react";
import { api } from "./api.js";
import CustomerPortal from "./CustomerPortal.jsx";
import SpecialistConsole from "./SpecialistConsole.jsx";

function currentView() {
  return window.location.hash === "#/specialist" ? "specialist" : "customer";
}

export default function App() {
  const [view, setView] = useState(currentView);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    const onHashChange = () => setView(currentView());
    window.addEventListener("hashchange", onHashChange);
    api("/api/config").then(setConfig).catch(() => setConfig(null));
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">MMAUG BOOTCAMP · 27 OCTOBER 2026</p>
          <h1>Customer Support Agent</h1>
        </div>
        <nav aria-label="Main">
          <a href="#/" aria-current={view === "customer" ? "page" : undefined}>Get help</a>
          <a href="#/specialist" aria-current={view === "specialist" ? "page" : undefined}>
            Specialist console
          </a>
        </nav>
      </header>
      <main>{view === "specialist" ? <SpecialistConsole config={config} /> : <CustomerPortal config={config} />}</main>
      <footer className="muted">
        AI drafts every reply from the knowledge base in Azure Blob Storage; a human specialist approves it
        before you see it.{" "}
        {config && <span>AI mode: <strong>{config.ai_mode}</strong>.</span>} Teaching app: no production
        customer authentication.
      </footer>
    </div>
  );
}
