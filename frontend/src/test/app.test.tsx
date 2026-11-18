import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { ChatView } from "../components/jocasta/ChatView";
import { useJocasta } from "../components/jocasta/useJocasta";
import { ThemeToggle } from "../components/layout/AppLayout";
import { ProtectedRoute } from "../components/layout/ProtectedRoute";
import { ErrorState } from "../components/ui";
import { tokenStore } from "../lib/api";
import { money } from "../lib/format";
import { Login, Register } from "../pages/Auth";
import Savings from "../pages/Savings";
import { TransactionModal } from "../pages/Transactions";
import Budgets from "../pages/Budgets";
import { mockApi, renderApp, USER } from "./utils";

describe("formatting", () => {
  it("formats INR with Indian grouping and handles negatives", () => {
    expect(money("221529.50", "INR")).toBe("₹2,21,529.50");
    expect(money("-500", "INR")).toBe("−₹500.00");
    expect(money("1200", "USD", { decimals: false })).toBe("$1,200");
  });
});

describe("theme switching", () => {
  it("toggles data-theme and persists preference", async () => {
    renderApp(<ThemeToggle />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    await userEvent.click(screen.getByRole("button", { name: /switch to dark theme/i }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("fm-theme")).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: /switch to light theme/i }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});

describe("authentication & navigation", () => {
  it("redirects unauthenticated users from the app to login", async () => {
    mockApi({});
    renderApp(
      <Routes>
        <Route path="/app" element={<ProtectedRoute><p>secret dashboard</p></ProtectedRoute>} />
        <Route path="/login" element={<p>login page</p>} />
      </Routes>, { route: "/app" });
    expect(await screen.findByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("secret dashboard")).not.toBeInTheDocument();
  });

  it("validates and logs in, storing the token", async () => {
    const calls = mockApi({ "POST /auth/login": { access_token: "tok123", token_type: "bearer", expires_in: 1800, user: USER } });
    renderApp(<Routes><Route path="/login" element={<Login />} /><Route path="/app" element={<p>welcome dashboard</p>} /></Routes>, { route: "/login" });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Secure123pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("welcome dashboard")).toBeInTheDocument();
    expect(tokenStore.get()).toBe("tok123");
    expect(calls[0]).toMatchObject({ method: "POST", path: "/auth/login", body: { email: "a@example.com", password: "Secure123pass" } });
  });

  it("shows the server error on bad credentials", async () => {
    mockApi({ "POST /auth/login": () => ({ status: 401, body: { error: { code: "invalid_credentials", message: "Incorrect email or password" } } }) });
    renderApp(<Login />, { route: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpass1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  });

  it("registration enforces password rules and matching", async () => {
    mockApi({});
    renderApp(<Register />, { route: "/register" });
    await userEvent.type(screen.getByLabelText("Full name"), "Asha");
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.type(screen.getByLabelText("Confirm password"), "different1");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Include a number")).toBeInTheDocument();
    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
  });
});

const CATS = [
  { id: "c-food", name: "Food and Groceries", slug: "food", kind: "expense", color: "#A58B58", icon: null, is_system: true },
  { id: "c-inc", name: "Income", slug: "income", kind: "income", color: "#5A6751", icon: null, is_system: true },
];

describe("transaction operations", () => {
  it("submits a new transaction with exact decimal string amount", async () => {
    const calls = mockApi({ "GET /categories": CATS, "POST /transactions": () => ({ status: 201, body: { id: "t1" } }) });
    const onClose = vi.fn();
    renderApp(<TransactionModal open onClose={onClose} />);
    await userEvent.type(screen.getByLabelText("Description"), "Groceries");
    await userEvent.type(screen.getByLabelText(/Amount/), "-5");
    await userEvent.click(screen.getByRole("button", { name: "Add transaction" }));
    expect(await screen.findByText(/positive amount/)).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText(/Amount/));
    await userEvent.type(screen.getByLabelText(/Amount/), "500.10");
    await waitFor(() => expect(screen.getByRole("option", { name: "Food and Groceries" })).toBeInTheDocument());
    await userEvent.selectOptions(screen.getByLabelText("Category"), "c-food");
    await userEvent.click(screen.getByRole("button", { name: "Add transaction" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.body).toMatchObject({ description: "Groceries", amount: "500.10", type: "expense", category_id: "c-food" });
  });
});

describe("budget operations", () => {
  const budget = { id: "b1", category: CATS[0], month: "2026-11-01", amount: "4000.00", notes: null, spent: "4500.00", remaining: "-500.00", utilization: "112.5", status: "exceeded" };
  it("shows utilisation, exceeded status and approves a recommendation", async () => {
    const rec = { id: "r1", category: CATS[0], month: "2026-12-01", proposed_amount: "5100.00", historical_basis: { months: [{ month: "2026-10-01", amount: "5000" }], weighted_average: "5000", mean: "5000", trend_per_month: "0", months_with_data: 1, method: "x" },
      reason: "Based on history", expected_effect: "Realistic", confidence: "low", limitations: "Limited history", status: "pending", created_at: "2026-11-18" };
    const calls = mockApi({
      "GET /budgets": { month: "2026-11-01", items: [budget], previous_month: [], totals: { budgeted: "4000.00", spent: "4500.00", remaining: "-500.00", utilization: "112.5" } },
      "GET /budgets/recommendations": [rec], "GET /categories": CATS,
      "POST /budgets/recommendations/r1/decision": { status: "approved", budget_id: "b2" },
    });
    renderApp(<Budgets />);
    expect(await screen.findByText("Exceeded")).toBeInTheDocument();
    expect(screen.getByText("112.5% used")).toBeInTheDocument();
    expect(screen.getByText("Based on history")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(calls.some((c) => c.path === "/budgets/recommendations/r1/decision" && (c.body as { approve: boolean }).approve)).toBe(true));
  });
});

describe("savings operations", () => {
  it("lists goals with required monthly saving and validates new goals", async () => {
    const goal = { id: "g1", name: "New laptop", target_amount: "60000.00", current_amount: "20000.00", target_date: "2027-07-18", status: "active", notes: null,
      created_at: "2026-11-01", remaining_amount: "40000.00", progress_percent: "33.3", months_remaining: 8, required_monthly: "5000.00", on_track: true, contributions: [] };
    const calls = mockApi({ "GET /savings": [goal], "POST /savings": () => ({ status: 201, body: goal }) });
    renderApp(<Savings />);
    expect(await screen.findByText("New laptop")).toBeInTheDocument();
    expect(screen.getByText("₹5,000.00")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /New goal/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save goal" }));
    expect(await within(dialog).findByText("Give the goal a name")).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText("Goal"), "Trip");
    await userEvent.type(within(dialog).getByLabelText("Target amount"), "35000");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save goal" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/savings")).toBe(true));
  });
});

function ChatHarness() {
  const chat = useJocasta(null);
  return <div style={{ height: 600 }}><ChatView chat={chat} /></div>;
}

describe("JOCASTA interactions", () => {
  it("sends a message, renders a confirmation card and confirms it", async () => {
    tokenStore.set("tok");
    const confirmCard = { type: "confirmation", confirmation_id: "pc1", action: "create_transaction", status: "pending",
      summary: { title: "New transaction", fields: { Category: "Food and Groceries", Amount: "INR 500.00", Date: "2026-11-18" } } };
    const calls = mockApi({
      "GET /users/me": USER,
      "GET /assistant/status": { available: true, model: "openai/gpt-oss-120b" },
      "GET /assistant/suggestions": { suggestions: ["Add ₹500 for groceries today"] },
      "POST /assistant/chat": { conversation_id: "conv1", message: { id: "m1", role: "assistant", content: "I've prepared a new transaction. Should I add it?", created_at: "x",
        meta: { cards: [confirmCard], tool_events: [{ tool: "create_transaction", status: "confirmation_required" }] } } },
      "POST /assistant/confirmations/pc1/confirm": { conversation_id: "conv1", message: { id: "m2", role: "assistant", content: "Done. I've added the transaction.", created_at: "y",
        meta: { cards: [{ type: "transaction_result", operation: "created", record: { description: "Groceries", amount: "500.00", category: "Food and Groceries", date: "2026-11-18", type: "expense" } }], resolved_confirmation: { id: "pc1", status: "confirmed" } } } },
    });
    renderApp(<ChatHarness />);
    await userEvent.click(await screen.findByRole("button", { name: "Add ₹500 for groceries today" }));
    expect(await screen.findByText(/Should I add it\?/)).toBeInTheDocument();
    expect(screen.getByText("Preparing transaction")).toBeInTheDocument();
    expect(screen.getByText("Food and Groceries")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Confirm$/ }));
    expect(await screen.findByText("Done. I've added the transaction.")).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/assistant/confirmations/pc1/confirm")).toBe(true);
    expect(calls.find((c) => c.path === "/assistant/chat")!.body).toEqual({ message: "Add ₹500 for groceries today", conversation_id: null });
  });

  it("shows an error state when the assistant request fails", async () => {
    tokenStore.set("tok");
    mockApi({ "GET /users/me": USER, "GET /assistant/status": { available: true }, "GET /assistant/suggestions": { suggestions: [] },
      "POST /assistant/chat": () => ({ status: 429, body: { error: { code: "rate_limited", message: "slow down" } } }) });
    renderApp(<ChatHarness />);
    const input = await screen.findByLabelText("Message JOCASTA");
    await userEvent.type(input, "hello{enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Too many requests/);
  });
});

describe("loading and error states", () => {
  it("renders an error with retry", async () => {
    const retry = vi.fn();
    renderApp(<ErrorState error={new Error("Database unavailable")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Database unavailable");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Try again" })); });
    expect(retry).toHaveBeenCalled();
  });
});
