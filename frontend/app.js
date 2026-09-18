const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 52;
const SUBSYSTEM_ORDER = ["door", "acv", "rail_corrugation", "shm"];
// Rail Corrugation and SHM must submit one predictions.csv covering every
// test file, so their tab accepts a batch upload. Door (one continuous
// stream) and ACV (a single held-out file) stay single-file. Must match
// MULTI_FILE_SUBSYSTEMS in backend/app.py.
const MULTI_FILE_SUBSYSTEMS = ["rail_corrugation", "shm"];

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
  const isMulti = MULTI_FILE_SUBSYSTEMS.includes(name);

  panel.innerHTML = `
    <div class="card">
      <h2>${meta.label}</h2>
      <p class="hint">${meta.input_hint}</p>
      ${
        isMulti
          ? `<p class="hint">Select all test files at once — every file's prediction is combined into one downloadable CSV.</p>`
          : ""
      }
      <div class="upload-row">
        <input type="file" id="file-input" accept="${meta.allowed_extensions.join(",")}" ${isMulti ? "multiple" : ""} />
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

  const isMulti = MULTI_FILE_SUBSYSTEMS.includes(name);
  statusEl.classList.remove("error");

  if (!fileInput.files.length) {
    statusEl.textContent = isMulti ? "Choose at least one file first." : "Choose a file first.";
    statusEl.classList.add("error");
    return;
  }

  const formData = new FormData();
  Array.from(fileInput.files).forEach((f) => formData.append("file", f));

  runBtn.disabled = true;
  statusEl.classList.add("processing");
  const fileWord = fileInput.files.length > 1 ? `${fileInput.files.length} files` : "your file";
  statusEl.innerHTML = `<span class="spinner"></span>Processing ${fileWord}… this can take up to a minute or two for larger files.`;
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
    statusEl.classList.remove("processing");
    statusEl.textContent = "Done.";
    renderResult(name, data);
  } catch (err) {
    statusEl.classList.remove("processing");
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
    ${
      data.file_count
        ? `<p class="hint">Combined across ${data.file_count} files — average health score, alert if any file triggered one.</p>`
        : ""
    }
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
  return `<div class="table-scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
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
