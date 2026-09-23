"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type OutputFormat = "human" | "json";
type RunState = "idle" | "loading" | "ready" | "error";

type ApiResponse = {
  format: OutputFormat;
  result: string | Record<string, unknown>;
  response_id?: string | null;
  research_id?: number | null;
};

type HealthResponse = {
  openai_configured?: boolean;
  provider?: string;
  provider_configured?: boolean;
};

type HistoryItem = {
  id: number;
  question: string;
  output_format: OutputFormat;
  result?: string;
  sources?: string[];
  created_at: string;
};

type UserProfile = {
  id: number;
  email: string;
  created_at: string;
};

const suggestions = [
  "Does drinking coffee cause dehydration in regular consumers?",
  "Is there clinical evidence that intermittent fasting is superior for long-term weight loss?",
  "What are the mandatory compliance requirements for high-risk AI under the EU AI Act?",
];

const progressStages = [
  "Scoping the question",
  "Searching live authoritative sources",
  "Cross-checking evidence & counter-claims",
  "Synthesizing verified dossier",
];

function resultText(response: ApiResponse): string {
  return response.format === "json"
    ? JSON.stringify(response.result, null, 2)
    : String(response.result);
}

function renderWithLinks(text: string) {
  return text.split(/(https?:\/\/[^\s)\]>]+)/g).map((part, index) =>
    /^https?:\/\//.test(part) ? (
      <a key={`${part}-${index}`} href={part} target="_blank" rel="noreferrer">
        {part}
      </a>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  );
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [format, setFormat] = useState<OutputFormat>("human");
  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState("");
  const [liveWeb, setLiveWeb] = useState(true);
  const [runState, setRunState] = useState<RunState>("idle");
  const [response, setResponse] = useState<ApiResponse | null>(null);
  const [lastResearchId, setLastResearchId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [followUp, setFollowUp] = useState("");
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Authentication State
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Load stored token on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("dossier_auth_token");
    if (savedToken) {
      setAuthToken(savedToken);
      fetchCurrentUser(savedToken);
    }
  }, []);

  async function fetchCurrentUser(token: string) {
    try {
      const res = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = (await res.json()) as { user: UserProfile };
        setCurrentUser(data.user);
      } else {
        localStorage.removeItem("dossier_auth_token");
        setAuthToken(null);
        setCurrentUser(null);
      }
    } catch {
      // offline or server unavailable
    }
  }

  async function loadHistory(token: string | null = authToken) {
    try {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const result = await fetch("/api/history", { headers });
      if (!result.ok) return;
      const payload = (await result.json()) as { items?: HistoryItem[] };
      setHistory(payload.items ?? []);
    } catch {
      // history fetch fail
    }
  }

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json() as Promise<HealthResponse>)
      .then((health) => {
        setApiReady(health.provider_configured !== false);
        if (health.provider) setProvider(health.provider);
      })
      .catch(() => setApiReady(null));
    loadHistory(authToken);
  }, [authToken]);

  async function handleAuthSubmit(e: FormEvent) {
    e.preventDefault();
    setAuthError("");
    setAuthLoading(true);
    const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed.");
      }
      localStorage.setItem("dossier_auth_token", data.token);
      setAuthToken(data.token);
      setCurrentUser(data.user);
      setShowAuthModal(false);
      setAuthPassword("");
      loadHistory(data.token);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "Authentication error");
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    if (authToken) {
      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${authToken}` },
        });
      } catch {
        // pass
      }
    }
    localStorage.removeItem("dossier_auth_token");
    setAuthToken(null);
    setCurrentUser(null);
    loadHistory(null);
  }

  const displayedResult = useMemo(
    () => (response ? resultText(response) : ""),
    [response],
  );

  async function investigate(trimmedQuestion: string, followUpOf: number | null = null) {
    setRunState("loading");
    setResponse(null);
    setError("");
    setCopied(false);

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const result = await fetch("/api/research", {
        method: "POST",
        headers,
        body: JSON.stringify({
          question: trimmedQuestion,
          output_format: format,
          model: model.trim() || null,
          provider,
          live_web: liveWeb,
          follow_up_of: followUpOf,
        }),
      });
      const payload = (await result.json()) as ApiResponse & { detail?: string };
      if (!result.ok) throw new Error(payload.detail || "The research request failed.");
      setResponse(payload);
      setLastResearchId(payload.research_id ?? null);
      setRunState("ready");
      loadHistory(authToken);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Something went wrong.");
      setRunState("error");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || runState === "loading") return;
    await investigate(trimmedQuestion);
  }

  async function copyResult() {
    await navigator.clipboard.writeText(displayedResult);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function downloadResult(extension: "md" | "json") {
    if (!response) return;
    const body = extension === "json"
      ? JSON.stringify({ question, result: response.result, response_id: response.response_id }, null, 2)
      : `# Dossier Research Report\n\n**Question:** ${question}\n\n${displayedResult}\n`;
    const blob = new Blob([body], { type: extension === "json" ? "application/json" : "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `dossier-${new Date().toISOString().slice(0, 10)}.${extension}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function runFollowUp() {
    const trimmedFollowUp = followUp.trim();
    if (!trimmedFollowUp || runState === "loading") return;
    const nextQuestion = `${question.trim()}\n\nFollow-up request: ${trimmedFollowUp}`;
    setQuestion(nextQuestion);
    setFollowUp("");
    await investigate(nextQuestion, lastResearchId);
  }

  function inspectHistoryItem(item: HistoryItem) {
    setQuestion(item.question);
    if (item.result) {
      let parsed: string | Record<string, unknown> = item.result;
      if (item.output_format === "json") {
        try {
          parsed = JSON.parse(item.result);
        } catch {
          parsed = item.result;
        }
      }
      setResponse({
        format: item.output_format,
        result: parsed,
        research_id: item.id,
      });
      setLastResearchId(item.id);
      setRunState("ready");
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Dossier home">
          <span className="brand-mark">D</span>
          <span>Dossier</span>
        </a>
        <div className="topbar-right">
          <div className={`topbar-meta ${apiReady === false ? "needs-config" : ""}`}>
            <span className={apiReady === false ? "status-warning" : "live-dot"} />
            {apiReady === false ? "API key needed" : apiReady === null ? "Connecting" : "DuckDuckGo Live Search"}
          </div>

          <div className="auth-status">
            {currentUser ? (
              <div className="user-badge-wrap">
                <span className="user-email" title={currentUser.email}>
                  👤 {currentUser.email.split("@")[0]}
                </span>
                <button type="button" className="auth-btn auth-btn-secondary" onClick={handleLogout}>
                  Sign out
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="auth-btn auth-btn-primary"
                onClick={() => {
                  setAuthMode("login");
                  setAuthError("");
                  setShowAuthModal(true);
                }}
              >
                Sign in / Register
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="modal-backdrop" onClick={() => setShowAuthModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{authMode === "login" ? "Sign in to Dossier" : "Create an Account"}</h3>
              <button type="button" className="modal-close" onClick={() => setShowAuthModal(false)}>
                ✕
              </button>
            </div>
            <p className="modal-sub">
              {authMode === "login"
                ? "Sign in to access and store your research history securely."
                : "Register to save your investigations and access them across sessions."}
            </p>

            <form onSubmit={handleAuthSubmit} className="modal-form">
              <label>
                <span>Email address</span>
                <input
                  type="email"
                  required
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                />
              </label>

              <label>
                <span>Password</span>
                <input
                  type="password"
                  required
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  autoComplete={authMode === "login" ? "current-password" : "new-password"}
                />
              </label>

              {authError && <p className="error">{authError}</p>}

              <button type="submit" className="modal-submit-btn" disabled={authLoading}>
                {authLoading ? "Processing..." : authMode === "login" ? "Sign in" : "Create account"}
              </button>
            </form>

            <div className="modal-footer">
              {authMode === "login" ? (
                <p>
                  Don&apos;t have an account?{" "}
                  <button
                    type="button"
                    className="modal-link"
                    onClick={() => {
                      setAuthMode("register");
                      setAuthError("");
                    }}
                  >
                    Register here
                  </button>
                </p>
              ) : (
                <p>
                  Already have an account?{" "}
                  <button
                    type="button"
                    className="modal-link"
                    onClick={() => {
                      setAuthMode("login");
                      setAuthError("");
                    }}
                  >
                    Sign in here
                  </button>
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <section className="hero">
        <p className="eyebrow">DEEP RESEARCH / LIVE FACT CHECKING</p>
        <h1>
          Ask a question.
          <br />
          <em>Get the evidence.</em>
        </h1>
        <p className="hero-copy">
          Dossier searches DuckDuckGo live sources, cross-checks claims, and makes confidence & caveats transparent.
        </p>
        <div className="hero-trust">
          <span>DuckDuckGo Live Search</span>
          <span>OpenRouter & DeepSeek Support</span>
          <span>Durable SQLite Accounts</span>
        </div>
      </section>

      <section className="workspace" aria-label="Research workspace">
        <form className="research-card" onSubmit={handleSubmit}>
          <div className="card-heading">
            <div>
              <span className="step-number">01</span>
              <span className="heading-label">Your research brief</span>
            </div>
            <span className="key-hint">⌘ ↵ to run</span>
          </div>
          <label className="sr-only" htmlFor="question">Question or claim to research</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") event.currentTarget.form?.requestSubmit();
            }}
            rows={6}
            required
            maxLength={10000}
            aria-describedby="question-help"
            placeholder="What claim or question would you like to verify?"
          />
          <p id="question-help" className="field-help">
            Enter a factual claim or question. Dossier queries live sources and structures verified verdicts.
          </p>
          <div className="suggestions" aria-label="Example questions">
            {suggestions.map((suggestion) => (
              <button key={suggestion} type="button" className="suggestion" onClick={() => setQuestion(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
          <div className="controls">
            <label className="select-wrap" htmlFor="provider">
              <span>Provider</span>
              <select id="provider" value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="openrouter">OpenRouter free</option>
                <option value="deepseek">DeepSeek API</option>
                <option value="local">Local vLLM / Qwen</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>
            <label className="select-wrap" htmlFor="output-format">
              <span>Output</span>
              <select id="output-format" value={format} onChange={(event) => setFormat(event.target.value as OutputFormat)}>
                <option value="human">Research report</option>
                <option value="json">Structured JSON</option>
              </select>
            </label>
            <label className="select-wrap model-control" htmlFor="model">
              <span>Model <small>optional</small></span>
              <input id="model" value={model} onChange={(event) => setModel(event.target.value)} placeholder="Default model" autoComplete="off" />
            </label>
            <label className="toggle-wrap">
              <input type="checkbox" checked={liveWeb} onChange={(event) => setLiveWeb(event.target.checked)} />
              <span className="toggle" aria-hidden="true" />
              <span>Live web (DDG)</span>
            </label>
            <button className="run-button" type="submit" disabled={runState === "loading"}>
              {runState === "loading" ? <><span className="spinner" /> Researching</> : <>Investigate <span className="arrow">↗</span></>}
            </button>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
        </form>

        <section className="result-card" aria-live="polite">
          {runState === "idle" && (
            <div className="result-empty">
              <div className="empty-icon">✦</div>
              <p className="empty-kicker">YOUR DOSSIER WILL APPEAR HERE</p>
              <p className="empty-copy">Start with a question that has a claim, a date, or a decision behind it.</p>
              <div className="empty-steps"><span><b>01</b> Scope</span><span><b>02</b> DDG Search</span><span><b>03</b> Cross-check</span><span><b>04</b> Report</span></div>
            </div>
          )}
          {runState === "loading" && (
            <div className="result-content result-working">
              <div className="result-toolbar"><span className="result-title">Building your dossier</span><span className="result-meta live-label"><span className="pulse-dot" /> Live Web Search</span></div>
              <div className="research-progress">
                {progressStages.map((stage, index) => (
                  <div className={`progress-line ${index === 1 ? "active" : ""}`} key={stage}>
                    <span className="progress-number">0{index + 1}</span><span>{stage}</span><span className={index === 1 ? "progress-spinner" : "progress-check"}>{index === 0 ? "✓" : index === 1 ? "" : "—"}</span>
                  </div>
                ))}
              </div>
              <p className="working-note">Searching live sources and cross-checking claims...</p>
            </div>
          )}
          {runState === "ready" && response && (
            <div className="result-content result-ready">
              <div className="result-toolbar">
                <span className="result-title">Research dossier</span>
                <div className="result-actions">
                  <span className="result-meta">{response.response_id ? "Verified report" : "Completed"}</span>
                  <button type="button" className="copy-button" onClick={copyResult}>{copied ? "Copied" : "Copy"}</button>
                  <button type="button" className="copy-button" onClick={() => downloadResult("md")}>.md</button>
                  <button type="button" className="copy-button" onClick={() => downloadResult("json")}>.json</button>
                </div>
              </div>
              <pre className="report">{renderWithLinks(displayedResult)}</pre>
              <div className="follow-up">
                <label htmlFor="follow-up">Continue this research</label>
                <div className="follow-up-row">
                  <input id="follow-up" value={followUp} onChange={(event) => setFollowUp(event.target.value)} placeholder="Ask a focused follow-up question" onKeyDown={(event) => { if (event.key === "Enter") void runFollowUp(); }} />
                  <button type="button" className="copy-button follow-up-button" onClick={() => void runFollowUp()} disabled={!followUp.trim()}>Run follow-up</button>
                </div>
              </div>
            </div>
          )}
          {runState === "error" && (
            <div className="result-content result-failure">
              <div className="failure-icon">!</div>
              <p className="result-title">The dossier could not be completed</p>
              <p className="failure-message">{error}</p>
              <p className="failure-help">Check network connectivity and provider configuration, then retry.</p>
            </div>
          )}
        </section>
      </section>

      <section className="history-panel" aria-label="Recent research history">
        <div className="history-heading">
          <div><span className="step-number">02</span><span className="heading-label">Recent research</span></div>
          <span className="history-note">{currentUser ? `Saved for ${currentUser.email}` : "Local / Shared history"}</span>
        </div>
        {history.length === 0 ? (
          <p className="history-empty">Your researched topics will appear here as you investigate them.</p>
        ) : (
          <div className="history-list">
            {history.map((item) => (
              <div className="history-item" key={`${item.id}-${item.created_at}`}>
                <div className="history-copy">
                  <span className="history-format">{item.output_format === "json" ? "JSON" : "REPORT"}</span>
                  <span className="history-question" onClick={() => inspectHistoryItem(item)} style={{ cursor: "pointer" }}>
                    {item.question}
                  </span>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <button type="button" className="history-revisit" onClick={() => inspectHistoryItem(item)}>
                    View <span>👁</span>
                  </button>
                  <button type="button" className="history-revisit" onClick={() => setQuestion(item.question)}>
                    Re-run <span>↗</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <footer className="footer"><span>Dossier 2026</span><span>Sources are cited inline · Verify high-stakes decisions independently</span></footer>
    </main>
  );
}
