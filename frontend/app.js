const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 52;
const SUBSYSTEM_ORDER = ["door", "acv", "rail_corrugation", "shm"];

const state = {
  subsystems: {},
  active: null,
  lastResult: null,
};

async function loadSubsystems() {
  const res = await fetch("/api/subsystems");
  state.subsystems = await res.json();

  const names = SUBSYSTEM_ORDER.filter((n) => n in state.subsystems).concat(
    Object.keys(state.subsystems).filter((n) => !SUBSYSTEM_ORDER.includes(n))
  );

  renderTabs(names);
  if (names.length) selectSubsystem(names[0]);
}

function renderTabs(names) {
  const tabBar = document.getElementById("tab-bar");
  tabBar.innerHTML = "";
  names.forEach((name) => {
    const btn = document.createElement("button");
    btn.className = "tab";
    btn.textContent = state.subsystems[name].label;
    btn.dataset.name = name;
    btn.addEventListener("click", () => selectSubsystem(name));
    tabBar.appendChild(btn);
  });
}

function selectSubsystem(name) {
  state.active = name;
  state.lastResult = null;
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.name === name);
  });
  renderPanel(name);
}

function renderPanel(name) {
  const meta = state.subsystems[name];
  const panel = document.getElementById("panel");

  panel.innerHTML = `
    <div class="card">
      <h2>${meta.label}</h2>
      <p class="hint">${meta.input_hint}</p>
      <div class="upload-row">
        <input type="file" id="file-input" accept="${meta.allowed_extensions.join(",")}" />
        <button id="run-btn">Run</button>
      </div>
      <div id="status" class="status"></div>
      <div id="result" class="result" hidden></div>
    </div>
  `;

  document.getElementById("run-btn").addEventListener("click", () => runPrediction(name));
}

async function runPrediction(name) {
  const fileInput = document.getElementById("file-input");
  const statusEl = document.getElementById("status");
  const runBtn = document.getElementById("run-btn");
  const resultEl = document.getElementById("result");

  statusEl.classList.remove("error");

  if (!fileInput.files.length) {
    statusEl.textContent = "Choose a file first.";
    statusEl.classList.add("error");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  runBtn.disabled = true;
  statusEl.textContent = "Running…";
  resultEl.hidden = true;

  try {
    const res = await fetch(`/api/predict/${name}`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    state.lastResult = data;
    statusEl.textContent = "Done.";
    renderResult(name, data);
  } catch (err) {
    statusEl.textContent = err.message;
    statusEl.classList.add("error");
  } finally {
    runBtn.disabled = false;
  }
}

function renderResult(name, data) {
  const meta = state.subsystems[name];
  const resultEl = document.getElementById("result");
  resultEl.hidden = false;

  const score = data.health_score;
  const offset = GAUGE_CIRCUMFERENCE * (1 - score / 100);
  const gaugeColor = data.alert ? "var(--bad)" : "var(--good)";

  resultEl.innerHTML = `
    <div class="gauge-row">
      <div class="gauge">
        <svg viewBox="0 0 120 120">
          <circle class="gauge-bg" cx="60" cy="60" r="52"></circle>
          <circle class="gauge-fill" cx="60" cy="60" r="52"
            style="stroke-dashoffset: ${offset}; stroke: ${gaugeColor};"></circle>
        </svg>
        <div class="gauge-label">
          <span>${score}</span>
          <small>Health</small>
        </div>
      </div>
      <div class="badge ${data.alert ? "alert" : "ok"}">
        ${data.alert ? "⚠ Alert (score < 80)" : "✓ Normal"}
      </div>
    </div>
    ${renderTable(meta.output_columns, data.results)}
    <button id="download-btn" class="secondary" ${data.results.length ? "" : "disabled"}>
      Download CSV
    </button>
  `;

  document.getElementById("download-btn").addEventListener("click", () => downloadCsv(name));
}

function renderTable(columns, rows) {
  if (!rows.length) {
    return `<p class="empty-note">No rows predicted.</p>`;
  }
  const head = columns.map((c) => `<th>${c}</th>`).join("");
  const body = rows
    .map((row) => `<tr>${columns.map((c) => `<td>${row[c]}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function csvEscape(value) {
  const str = String(value ?? "");
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function downloadCsv(name) {
  const meta = state.subsystems[name];
  const data = state.lastResult;
  if (!data) return;

  const columns = meta.output_columns;
  const lines = [columns.join(",")];
  data.results.forEach((row) => {
    lines.push(columns.map((c) => csvEscape(row[c])).join(","));
  });

  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}_predictions.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

loadSubsystems();
