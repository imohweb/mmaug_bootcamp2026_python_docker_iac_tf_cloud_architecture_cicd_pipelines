import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";

const CONFIG = {
  service: "MMAUG Customer Support Agent",
  ai_mode: "off",
  teams: [
    { category: "billing", team: "Billing & Payments", specialist: "Aye Chan" },
    { category: "account", team: "Account & Security", specialist: "Su Mon" },
  ],
};
const TOKEN = "s".repeat(40);
const awaiting = {
  id: "SUP-ABCDEF1234",
  status: "awaiting_approval",
  created_at: "2026-10-27T09:00:00+00:00",
  updated_at: "2026-10-27T09:00:00+00:00",
  customer: { name: "Thandar", email: "thandar@example.com" },
  message: "I was charged twice.",
  category: "billing",
  priority: "normal",
  assigned_to: { id: "aye-chan", name: "Aye Chan", team: "Billing & Payments", category: "billing" },
  draft: { text: "Draft reply", source: "knowledge-template", sources: [{ document: "billing-and-payments.md", heading: "Refund policy" }] },
  response: null,
  history: [{ at: "2026-10-27T09:00:00+00:00", event: "created", detail: "Agent assigned billing." }],
};

function json(body, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

describe("customer portal", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("submits a request and shows the approved reply", async () => {
    const fetchMock = vi.fn((url, options = {}) => {
      if (url === "/api/config") return json(CONFIG);
      if (url === "/api/tickets" && options.method === "POST") {
        expect(JSON.parse(options.body)).toEqual({ name: "Thandar", email: "thandar@example.com", message: "I was charged twice." });
        return json({ ticket: { ...awaiting, team: "Billing & Payments", specialist: "Aye Chan" }, access_key: "key-123" }, 201);
      }
      if (url === "/api/tickets/SUP-ABCDEF1234") {
        expect(options.headers["X-Ticket-Key"]).toBe("key-123");
        return json({ id: awaiting.id, status: "responded", created_at: awaiting.created_at, message: awaiting.message,
          team: "Billing & Payments", specialist: "Aye Chan", response: "We refunded the duplicate." });
      }
      return json({ error: "unexpected" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Your name"), "Thandar");
    await user.type(screen.getByLabelText("Email"), "thandar@example.com");
    await user.type(screen.getByLabelText("Your question"), "I was charged twice.");
    await user.click(screen.getByRole("button", { name: "Send to support" }));

    expect(await screen.findByRole("status")).toHaveTextContent("key-123");
    expect(await screen.findByText("We refunded the duplicate.")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("mmaug-support-tickets"))).toEqual([{ id: "SUP-ABCDEF1234", key: "key-123" }]);
  });

  it("shows validation errors from the API", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => (url === "/api/config" ? json(CONFIG) : json({ error: "Enter a valid email address." }, 400))));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Your name"), "A");
    await user.type(screen.getByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Your question"), "Long enough question");
    await user.click(screen.getByRole("button", { name: "Send to support" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid email address.");
  });
});

describe("specialist console", () => {
  beforeEach(() => {
    window.location.hash = "#/specialist";
  });

  it("reviews, edits and approves the agent draft", async () => {
    let approvedBody;
    const fetchMock = vi.fn((url, options = {}) => {
      if (url === "/api/config") return json(CONFIG);
      expect(options.headers.Authorization).toBe(`Bearer ${TOKEN}`);
      if (url.startsWith("/api/specialist/tickets?")) return json({ tickets: approvedBody ? [] : [awaiting] });
      if (url === "/api/specialist/knowledge") return json({ documents: [{ name: "billing-and-payments.md", title: "Billing and payments", category: "billing", sections: ["Refund policy"] }] });
      if (url === `/api/specialist/tickets/${awaiting.id}/approve`) {
        approvedBody = JSON.parse(options.body);
        return json({ ...awaiting, status: "responded", response: approvedBody.response,
          history: [...awaiting.history, { at: "2026-10-27T10:00:00+00:00", event: "approved", detail: "Aye Chan edited and approved the reply." }] });
      }
      return json({ error: "unexpected" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Specialist token"), TOKEN);
    await user.click(screen.getByRole("button", { name: "Open console" }));
    expect(await screen.findByText("Billing and payments (1 sections)")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /SUP-ABCDEF1234/ }));

    const reply = screen.getByLabelText("Reply to customer");
    expect(reply).toHaveValue("Draft reply");
    await user.clear(reply);
    await user.type(reply, "Edited reply");
    await user.click(screen.getByRole("button", { name: "Approve & send" }));

    expect(await screen.findByText("Reply approved and delivered to the customer.")).toBeInTheDocument();
    expect(approvedBody).toEqual({ response: "Edited reply" });
    await waitFor(() => expect(screen.getByText(/edited and approved/)).toBeInTheDocument());
  });

  it("returns to sign-in when the token is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => (url === "/api/config" ? json(CONFIG) : json({ error: "A valid specialist bearer token is required." }, 401))));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Specialist token"), "x".repeat(32));
    await user.click(screen.getByRole("button", { name: "Open console" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A valid specialist bearer token is required.");
    expect(screen.getByLabelText("Specialist token")).toBeInTheDocument();
  });
});
