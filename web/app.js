const form = document.querySelector("#research-form");
const question = document.querySelector("#question");
const resultPanel = document.querySelector("#result-panel");
const submitButton = document.querySelector("#submit-button");
const errorBox = document.querySelector("#error");
const topbarMeta = document.querySelector(".topbar-meta");

document.querySelector("#year").textContent = new Date().getFullYear();

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    if (topbarMeta && health.openai_configured === false) {
      topbarMeta.innerHTML = '<span class="status-warning"></span> API key needed';
      topbarMeta.classList.add("needs-config");
    }
  } catch {
    if (topbarMeta) topbarMeta.textContent = "Server connection unavailable";
  }
}

checkHealth();

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    question.value = button.textContent;
    question.focus();
  });
});

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function linkify(value) {
  return escapeHtml(value).replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noreferrer">$1</a>'
  );
}

function showResult(payload) {
  const body = payload.format === "json"
    ? JSON.stringify(payload.result, null, 2)
    : payload.result;
  resultPanel.innerHTML = `
    <div class="result-content result-ready">
      <div class="result-toolbar">
        <span class="result-title">Research dossier</span>
        <div class="result-actions">
          <span class="result-meta">${payload.response_id ? "Verified response" : "Completed"}</span>
          <button type="button" class="copy-button" id="copy-result">Copy</button>
        </div>
      </div>
      <pre class="report">${linkify(body)}</pre>
    </div>`;
  document.querySelector("#copy-result").addEventListener("click", async (event) => {
    await navigator.clipboard.writeText(body);
    event.currentTarget.textContent = "Copied";
    setTimeout(() => { event.currentTarget.textContent = "Copy"; }, 1600);
  });
}

function showWorking() {
  resultPanel.innerHTML = `
    <div class="result-content result-working">
      <div class="result-toolbar">
        <span class="result-title">Building your dossier</span>
        <span class="result-meta live-label"><span class="pulse-dot"></span> Live</span>
      </div>
      <div class="research-progress">
        <div class="progress-line"><span class="progress-number">01</span><span>Scoping the question</span><span class="progress-check">✓</span></div>
        <div class="progress-line active"><span class="progress-number">02</span><span>Searching authoritative sources</span><span class="progress-spinner"></span></div>
        <div class="progress-line"><span class="progress-number">03</span><span>Cross-checking evidence</span><span class="progress-check">—</span></div>
        <div class="progress-line"><span class="progress-number">04</span><span>Writing the findings</span><span class="progress-check">—</span></div>
      </div>
      <p class="working-note">This can take a little longer for contested or time-sensitive questions.</p>
    </div>`;
}

function showFailure(message) {
  resultPanel.innerHTML = `
    <div class="result-content result-failure">
      <div class="failure-icon">!</div>
      <p class="result-title">The dossier could not be completed</p>
      <p class="failure-message">${escapeHtml(message)}</p>
      <p class="failure-help">Check the server terminal for details. If you are running locally, make sure <code>OPENAI_API_KEY</code> is set before starting <code>dossier-web</code>.</p>
    </div>`;
}

function setLoading(loading) {
  submitButton.disabled = loading;
  submitButton.classList.toggle("is-loading", loading);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  const value = question.value.trim();
  if (!value) return;
  showWorking();
  setLoading(true);
  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: value,
        output_format: document.querySelector("#output-format").value,
        model: document.querySelector("#model").value.trim() || null,
        live_web: document.querySelector("#live-web").checked,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "The research request failed.");
    showResult(payload);
  } catch (error) {
    const message = error.message || "Something went wrong. Try again.";
    errorBox.textContent = message;
    errorBox.hidden = false;
    showFailure(message);
  } finally {
    setLoading(false);
  }
});

question.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") form.requestSubmit();
});
