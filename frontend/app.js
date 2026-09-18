const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 52;
const SUBSYSTEM_ORDER = ["door", "acv", "rail_corrugation", "shm"];
// Rail Corrugation and SHM must submit one predictions.csv covering every
// test file, so their tab accepts a batch upload. Door (one continuous
// stream) and ACV (a single held-out file) stay single-file. Must match
// MULTI_FILE_SUBSYSTEMS in backend/app.py.
const MULTI_FILE_SUBSYSTEMS = ["rail_corrugation", "shm"];

// Filenames expected by the challenge submission format
// (docs/example_submissions/*.csv) — used by the Submission Centre and the
// predictions.zip packager. Independent of the internal subsystem key.
const SUBMISSION_FILENAMES = {
  door: "door_predictions.csv",
  acv: "acv_predictions.csv",
  rail_corrugation: "rail_predictions.csv",
  shm: "shm_predictions.csv",
};

// health_score >= 80 -> normal, >= 60 -> attention, else high priority.
// This is a client-side, presentation-only banding on top of the existing
// {health_score, alert} contract — it does not change what the backend
// returns or how alert (score < 80) is computed.
function severityFor(healthScore) {
  if (healthScore >= 80) return "normal";
  if (healthScore >= 60) return "attention";
  return "high";
}

const SEVERITY_META = {
  normal: { label: "Normal", icon: "✓", className: "sev-normal" },
  attention: { label: "Attention", icon: "⚠", className: "sev-attention" },
  high: { label: "High Priority", icon: "✖", className: "sev-high" },
  none: { label: "Not yet assessed", icon: "–", className: "sev-none" },
};

const state = {
  subsystems: {},
  active: null,
  lastResult: null,
  currentView: "overview",
  // In-memory, per-browser-tab session store. Resets on reload — this is
  // intentionally NOT persisted anywhere, and the UI labels it "Current
  // Session" rather than implying durable history.
  session: {
    filesAnalysed: 0,
    results: {}, // subsystem name -> { health_score, alert, results, fileCount, timestamp }
  },
};

async function loadSubsystems() {
  const res = await fetch("/api/subsystems");
  state.subsystems = await res.json();

  const names = SUBSYSTEM_ORDER.filter((n) => n in state.subsystems).concat(
    Object.keys(state.subsystems).filter((n) => !SUBSYSTEM_ORDER.includes(n))
  );

  renderTabs(names);
  if (names.length) selectSubsystem(names[0]);

  setupNav();
  setView("overview");
}

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });
}

function setView(view) {
  state.currentView = view;
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  document.getElementById("view-overview").hidden = view !== "overview";
  document.getElementById("view-assessment").hidden = view !== "assessment";
  document.getElementById("view-submission").hidden = view !== "submission";

  if (view === "overview") renderOverview();
  if (view === "submission") renderSubmissionCentre();
}

function goToSubsystem(name) {
  setView("assessment");
  selectSubsystem(name);
}

/* ---------------------------------------------------------------------- */
/* Overview                                                                */
/* ---------------------------------------------------------------------- */

function renderOverview() {
  const el = document.getElementById("view-overview");
  const names = SUBSYSTEM_ORDER.filter((n) => n in state.subsystems);
  const analysed = names.filter((n) => state.session.results[n]);

  const severities = analysed.map((n) => severityFor(state.session.results[n].health_score));
  const attentionCount = severities.filter((s) => s === "attention").length;
  const highCount = severities.filter((s) => s === "high").length;

  let overallSeverity = "none";
  if (analysed.length) {
    overallSeverity = highCount > 0 ? "high" : attentionCount > 0 ? "attention" : "normal";
  }

  el.innerHTML = `
    <div class="view-header">
      <h2>Train Condition Monitoring Platform</h2>
      <p class="hint">Upload subsystem sensor data, run the trained models, and review fleet condition at a glance.</p>
    </div>

    <div class="stat-grid">
      ${statCard(
        "Files Analysed",
        state.session.filesAnalysed > 0 ? String(state.session.filesAnalysed) : "No assessment yet",
        "this session"
      )}
      ${statCard(
        "Attention Cases",
        analysed.length ? String(attentionCount) : "No assessment yet",
        "score 60&ndash;79"
      )}
      ${statCard(
        "High Priority Cases",
        analysed.length ? String(highCount) : "No assessment yet",
        "score below 60"
      )}
      ${conditionIndicatorCard(overallSeverity)}
    </div>

    <div class="section-heading">
      <h3>Subsystems &mdash; Current Session</h3>
      <span class="section-sub">Latest result run in this browser session</span>
    </div>
    <div class="subsystem-grid">
      ${names.map((name) => subsystemStatusCard(name)).join("")}
    </div>
  `;

  el.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => goToSubsystem(btn.dataset.goto));
  });
}

function statCard(label, value, sub) {
  return `
    <div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
      <div class="stat-sub">${sub}</div>
    </div>
  `;
}

function conditionIndicatorCard(severity) {
  const meta = SEVERITY_META[severity];
  const note =
    "This indicator summarises model outputs for demonstration purposes. It is not an engineering certified reliability or safety threshold.";
  return `
    <div class="stat-card indicator-card ${meta.className}" title="${note}">
      <div class="stat-label">
        Prototype Condition Indicator
        <span class="info-dot" tabindex="0" aria-label="${note}">i</span>
      </div>
      <div class="stat-value"><span class="sev-icon">${meta.icon}</span> ${meta.label}</div>
      <div class="stat-sub indicator-note">${note}</div>
    </div>
  `;
}

function subsystemStatusCard(name) {
  const meta = state.subsystems[name];
  const result = state.session.results[name];

  if (!result) {
    return `
      <div class="card subsystem-card">
        <div class="subsystem-card-head">
          <h4>${meta.label}</h4>
          <span class="status-pill ${SEVERITY_META.none.className}">${SEVERITY_META.none.icon} ${SEVERITY_META.none.label}</span>
        </div>
        <p class="hint">${meta.input_hint}</p>
        <button class="secondary" data-goto="${name}">View Details</button>
      </div>
    `;
  }

  const sev = severityFor(result.health_score);
  const sevMeta = SEVERITY_META[sev];
  const action = computeRecommendedAction(name, result);

  return `
    <div class="card subsystem-card">
      <div class="subsystem-card-head">
        <h4>${meta.label}</h4>
        <span class="status-pill ${sevMeta.className}">${sevMeta.icon} ${sevMeta.label}</span>
      </div>
      <div class="subsystem-score">Health score: <strong>${result.health_score}</strong> / 100</div>
      <div class="subsystem-summary">${summaryLineFor(name, result)}</div>
      <div class="recommended-action">
        <span class="ra-label">Recommended action</span>
        <p>${action.text}</p>
      </div>
      <button class="secondary" data-goto="${name}">View Details</button>
    </div>
  `;
}

function summaryLineFor(name, result) {
  const rows = result.results;
  const n = rows.length;
  if (name === "door") {
    const abnormal = rows.filter((r) => r.prediction === "Abnormal resistance").length;
    return `${abnormal} of ${n} door cycles flagged abnormal`;
  }
  if (name === "acv") {
    const top = rows[0].ranked_cars.split("|")[0];
    return `Top-ranked (most likely faulty) car: Car ${top}`;
  }
  if (name === "rail_corrugation") {
    if (n === 1) return `Prediction: ${rows[0].prediction}`;
    const abnormal = rows.filter((r) => r.prediction !== "Normal").length;
    return `${abnormal} of ${n} files flagged Side I / Side II`;
  }
  if (name === "shm") {
    if (n === 1) return `Predicted cumulative damage: ${rows[0].prediction}`;
    const max = Math.max(...rows.map((r) => Number(r.prediction)));
    return `${n} files &mdash; highest predicted damage: ${max}`;
  }
  return "";
}

/* ---------------------------------------------------------------------- */
/* Recommended action                                                      */
/* ---------------------------------------------------------------------- */

function computeRecommendedAction(name, result) {
  const sev = severityFor(result.health_score);

  if (name === "door") {
    const rows = result.results;
    const abnormal = rows.filter((r) => r.prediction === "Abnormal resistance");
    if (abnormal.length === 0) {
      return { text: "Continue routine monitoring.", severity: "normal" };
    }
    const rate = abnormal.length / rows.length;
    const priorityWord = sev === "high" ? "High priority" : "Attention";
    return {
      text: `${priorityWord}: Inspect the door mechanism for possible obstruction, slide rail resistance, or misalignment (${abnormal.length} of ${rows.length} cycles flagged, ${Math.round(rate * 100)}% abnormal-cycle rate).`,
      severity: sev,
    };
  }

  if (name === "acv") {
    const topCar = result.results[0].ranked_cars.split("|")[0];
    return {
      text: `Inspect Car ${topCar}'s ACV cooling circuit first. Review refrigerant level and related temperature sensors.`,
      severity: sev,
    };
  }

  if (name === "rail_corrugation") {
    const sides = Array.from(new Set(result.results.map((r) => r.prediction).filter((p) => p !== "Normal")));
    if (sides.length === 0) {
      return { text: "Continue routine monitoring.", severity: "normal" };
    }
    return {
      text: `Review the ${sides.join(" and ")} rail condition and compare with track inspection records.`,
      severity: sev,
    };
  }

  if (name === "shm") {
    const rows = result.results.slice().sort((a, b) => Number(b.prediction) - Number(a.prediction));
    const topN = rows.slice(0, Math.min(3, rows.length));
    const fileList = topN.map((r) => `${r.file_id} (${r.prediction})`).join(", ");
    return {
      text: `Prioritise files with higher predicted cumulative damage for engineering review. Highest predicted damage: ${fileList}.`,
      severity: sev,
    };
  }

  return { text: "", severity: sev };
}

/* ---------------------------------------------------------------------- */
/* Submission Centre                                                       */
/* ---------------------------------------------------------------------- */

function renderSubmissionCentre() {
  const el = document.getElementById("view-submission");
  const names = SUBSYSTEM_ORDER.filter((n) => n in state.subsystems);
  const rows = names.map((name) => {
    const meta = state.subsystems[name];
    const result = state.session.results[name];
    return {
      name,
      label: meta.label,
      filename: SUBMISSION_FILENAMES[name],
      rowCount: result ? result.results.length : null,
      hasResult: !!result,
    };
  });
  const readyCount = rows.filter((r) => r.hasResult).length;

  el.innerHTML = `
    <div class="view-header">
      <h2>Submission Centre</h2>
      <p class="hint">Package this session's generated prediction CSVs into a single predictions.zip, with each file placed at the zip's top level.</p>
    </div>

    <div class="card submission-card">
      <div class="submission-list">
        ${rows
          .map(
            (r) => `
          <div class="submission-row ${r.hasResult ? "ready" : "pending"}">
            <div class="submission-cell submission-name">${r.label}</div>
            <div class="submission-cell submission-file">${r.hasResult ? r.filename : "Not yet generated"}</div>
            <div class="submission-cell submission-rows">${r.hasResult ? r.rowCount + " rows" : "&mdash;"}</div>
            <div class="submission-cell submission-status">
              <span class="status-pill ${r.hasResult ? SEVERITY_META.normal.className : SEVERITY_META.none.className}">
                ${r.hasResult ? "✓ Ready" : "– Pending"}
              </span>
            </div>
          </div>
        `
          )
          .join("")}
      </div>
      <div class="submission-actions">
        <button id="create-zip-btn" ${readyCount ? "" : "disabled"}>Create predictions.zip</button>
        <div id="zip-status" class="status"></div>
      </div>
    </div>
  `;

  const zipBtn = document.getElementById("create-zip-btn");
  if (zipBtn) zipBtn.addEventListener("click", createPredictionsZip);
}

async function createPredictionsZip() {
  const statusEl = document.getElementById("zip-status");
  const zip = new JSZip();
  let count = 0;

  SUBSYSTEM_ORDER.forEach((name) => {
    const result = state.session.results[name];
    if (!result) return;
    const meta = state.subsystems[name];
    const csv = buildCsv(meta.output_columns, result.results);
    // Placed at the zip root (no folder prefix) — required submission layout.
    zip.file(SUBMISSION_FILENAMES[name], csv);
    count += 1;
  });

  if (!count) return;

  statusEl.classList.remove("error");
  statusEl.textContent = "Building predictions.zip…";

  try {
    const blob = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "predictions.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    statusEl.textContent = `Done — packaged ${count} file${count > 1 ? "s" : ""} into predictions.zip.`;
  } catch (err) {
    statusEl.textContent = `Failed to build zip: ${err.message}`;
    statusEl.classList.add("error");
  }
}

/* ---------------------------------------------------------------------- */
/* New Assessment (existing 4-tab upload flow)                             */
/* ---------------------------------------------------------------------- */

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
  const existing = state.session.results[name];

  panel.innerHTML = `
    <div class="card">
      <h2>${meta.label}</h2>
      <p class="hint">${meta.input_hint}</p>
      ${
        isMulti
          ? `<p class="hint">Select all test files at once &mdash; every file's prediction is combined into one downloadable CSV.</p>`
          : ""
      }
      ${
        existing
          ? `<p class="hint session-note">This subsystem already has a result from earlier this session. Running again will replace it on the Overview page and in the Submission Centre.</p>`
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
    state.session.results[name] = data;
    state.session.filesAnalysed += fileInput.files.length;

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
  const sev = severityFor(score);
  const sevMeta = SEVERITY_META[sev];
  const offset = GAUGE_CIRCUMFERENCE * (1 - score / 100);
  const action = computeRecommendedAction(name, data);

  resultEl.innerHTML = `
    <div class="gauge-row">
      <div class="gauge">
        <svg viewBox="0 0 120 120">
          <circle class="gauge-bg" cx="60" cy="60" r="52"></circle>
          <circle class="gauge-fill sev-fill-${sev}" cx="60" cy="60" r="52"
            style="stroke-dashoffset: ${offset};"></circle>
        </svg>
        <div class="gauge-label">
          <span>${score}</span>
          <small>Health</small>
        </div>
      </div>
      <span class="status-pill ${sevMeta.className}">${sevMeta.icon} ${sevMeta.label}</span>
    </div>
    ${
      data.file_count
        ? `<p class="hint">Combined across ${data.file_count} files &mdash; average health score, alert if any file triggered one.</p>`
        : ""
    }
    <div class="recommended-action">
      <span class="ra-label">Recommended action</span>
      <p>${action.text}</p>
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
  return `<div class="table-scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function csvEscape(value) {
  const str = String(value ?? "");
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildCsv(columns, rows) {
  const lines = [columns.join(",")];
  rows.forEach((row) => {
    lines.push(columns.map((c) => csvEscape(row[c])).join(","));
  });
  return lines.join("\n");
}

function downloadCsv(name) {
  const meta = state.subsystems[name];
  const data = state.lastResult;
  if (!data) return;

  const csv = buildCsv(meta.output_columns, data.results);
  const blob = new Blob([csv], { type: "text/csv" });
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
