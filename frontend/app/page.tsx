"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type OutputFormat = "human" | "json";
type RunState = "idle" | "loading" | "ready" | "error";

type ApiResponse = {
  format: OutputFormat;
  result: string | Record<string, unknown>;
  response_id?: string | null;
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
  created_at: string;
};

const suggestions = [
  "Is this health claim supported by current evidence?",
  "What changed in this policy this year?",
  "Fact-check this statement and find missing context.",
];

const progressStages = [
  "Scoping the question",
  "Searching authoritative sources",
  "Cross-checking evidence",
  "Writing the findings",
];

function resultText(response: ApiResponse): string {
  return response.format === "json"
    ? JSON.stringify(response.result, null, 2)
    : String(response.result);
}

function renderWithLinks(text: string) {
  return text.split(/(https?:\/\/[^\s]+)/g).map((part, index) =>
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
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [liveWeb, setLiveWeb] = useState(true);
  const [runState, setRunState] = useState<RunState>("idle");
  const [response, setResponse] = useState<ApiResponse | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [followUp, setFollowUp] = useState("");
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  async function loadHistory() {
    try {
      const result = await fetch("/api/history");
      if (!result.ok) return;
      const payload = (await result.json()) as { items?: HistoryItem[] };
      setHistory(payload.items ?? []);
    } catch {
      // History is a convenience panel; research remains usable if it is unavailable.
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
    loadHistory();
  }, []);

  const displayedResult = useMemo(
    () => (response ? resultText(response) : ""),
    [response],
  );

  async function investigate(trimmedQuestion: string) {
    setRunState("loading");
    setResponse(null);
    setError("");
    setCopied(false);

    try {
      const result = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmedQuestion,
          output_format: format,
          model: model.trim() || null,
          provider,
          live_web: liveWeb,
        }),
      });
      const payload = (await result.json()) as ApiResponse & { detail?: string };
      if (!result.ok) throw new Error(payload.detail || "The research request failed.");
      setResponse(payload);
      setRunState("ready");
      loadHistory();
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
    await investigate(nextQuestion);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Dossier home">
          <span className="brand-mark">D</span>
          <span>Dossier</span>
        </a>
        <div className={`topbar-meta ${apiReady === false ? "needs-config" : ""}`}>
          <span className={apiReady === false ? "status-warning" : "live-dot"} />
          {apiReady === false ? "API key needed" : apiReady === null ? "Checking connection" : "Evidence-first research"}
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">DEEP RESEARCH / FACT CHECKING</p>
        <h1>
          Ask a question.
          <br />
          <em>Get the evidence.</em>
        </h1>
        <p className="hero-copy">Dossier searches live sources, cross-checks claims, and makes uncertainty visible.</p>
        <div className="hero-trust">
          <span>Primary sources first</span>
          <span>Counter-evidence included</span>
          <span>Uncertainty labeled</span>
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
            placeholder="What would you like to verify?"
          />
          <p id="question-help" className="field-help">Ask a question, paste a claim, or name a decision. Dossier will break it into checkable parts.</p>
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
                <option value="openai">OpenAI + web search</option>
                <option value="deepseek">DeepSeek API</option>
                <option value="local">Local vLLM / Qwen</option>
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
              <span>Live web</span>
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
              <div className="empty-steps"><span><b>01</b> Scope</span><span><b>02</b> Search</span><span><b>03</b> Cross-check</span><span><b>04</b> Report</span></div>
            </div>
          )}
          {runState === "loading" && (
            <div className="result-content result-working">
              <div className="result-toolbar"><span className="result-title">Building your dossier</span><span className="result-meta live-label"><span className="pulse-dot" /> Live</span></div>
              <div className="research-progress">
                {progressStages.map((stage, index) => (
                  <div className={`progress-line ${index === 1 ? "active" : ""}`} key={stage}>
                    <span className="progress-number">0{index + 1}</span><span>{stage}</span><span className={index === 1 ? "progress-spinner" : "progress-check"}>{index === 0 ? "✓" : index === 1 ? "" : "—"}</span>
                  </div>
                ))}
              </div>
              <p className="working-note">This can take a little longer for contested or time-sensitive questions.</p>
            </div>
          )}
          {runState === "ready" && response && (
            <div className="result-content result-ready">
              <div className="result-toolbar">
                <span className="result-title">Research dossier</span>
                <div className="result-actions"><span className="result-meta">{response.response_id ? "Verified response" : "Completed"}</span><button type="button" className="copy-button" onClick={copyResult}>{copied ? "Copied" : "Copy"}</button><button type="button" className="copy-button" onClick={() => downloadResult("md")}>.md</button><button type="button" className="copy-button" onClick={() => downloadResult("json")}>.json</button></div>
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
              <p className="failure-help">Configure the selected provider credential on the API service, then restart FastAPI.</p>
            </div>
          )}
        </section>
      </section>

      <section className="history-panel" aria-label="Recent research history">
        <div className="history-heading">
          <div><span className="step-number">02</span><span className="heading-label">Recent research</span></div>
          <span className="history-note">Current session</span>
        </div>
        {history.length === 0 ? (
          <p className="history-empty">Your researched topics will appear here as you investigate them.</p>
        ) : (
          <div className="history-list">
            {history.map((item) => (
              <div className="history-item" key={`${item.id}-${item.created_at}`}>
                <div className="history-copy"><span className="history-format">{item.output_format === "json" ? "JSON" : "REPORT"}</span><span className="history-question">{item.question}</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
                <button type="button" className="history-revisit" onClick={() => setQuestion(item.question)}>Research again <span>↗</span></button>
              </div>
            ))}
          </div>
        )}
      </section>

      <footer className="footer"><span>Dossier 2026</span><span>Sources are cited inline · Verify high-stakes decisions independently</span></footer>
    </main>
  );
}
