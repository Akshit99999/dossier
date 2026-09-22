const form = document.querySelector("#research-form");
const question = document.querySelector("#question");
const resultPanel = document.querySelector("#result-panel");
const submitButton = document.querySelector("#submit-button");
const errorBox = document.querySelector("#error");

document.querySelector("#year").textContent = new Date().getFullYear();

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
    <div class="result-content">
      <div class="result-toolbar">
        <span class="result-title">Research dossier</span>
        <button type="button" class="copy-button" id="copy-result">Copy</button>
      </div>
      <pre class="report">${linkify(body)}</pre>
    </div>`;
  document.querySelector("#copy-result").addEventListener("click", async (event) => {
    await navigator.clipboard.writeText(body);
    event.currentTarget.textContent = "Copied";
    setTimeout(() => { event.currentTarget.textContent = "Copy"; }, 1600);
  });
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
    errorBox.textContent = error.message || "Something went wrong. Try again.";
    errorBox.hidden = false;
  } finally {
    setLoading(false);
  }
});

question.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") form.requestSubmit();
});
