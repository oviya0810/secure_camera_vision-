/* Secure Camera Network dashboard - front-end logic */
const COLORS = ["#3da5ff", "#2fe08a", "#ffd23f", "#b07bff", "#ff9f40", "#ff4d5e"];
let charts = {};
let seenAlerts = new Set();

function msg(t, cls) {
  const m = document.getElementById("addMsg");
  m.textContent = t; m.className = "msg " + (cls || "");
  if (t) setTimeout(() => { m.textContent = ""; }, 4000);
}

async function addCamera() {
  const name = document.getElementById("camName").value;
  const source = document.getElementById("camSource").value;
  if (!source) return msg("Enter a stream link first", "err");
  const r = await fetch("/api/cameras", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, source })
  });
  const d = await r.json();
  if (r.ok) { msg("Camera added ✓", "ok"); document.getElementById("camName").value = "";
    document.getElementById("camSource").value = ""; refresh(); }
  else msg(d.error || "Failed to add", "err");
}

async function addWebcam() {
  const r = await fetch("/api/cameras", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Laptop Webcam", source: "webcam:0" })
  });
  if (r.ok) { msg("Webcam added ✓", "ok"); refresh(); } else msg("Failed", "err");
}

async function delCamera(id) {
  if (!confirm("Remove this camera?")) return;
  await fetch("/api/cameras/" + id, { method: "DELETE" });
  const el = document.getElementById("feed-" + id); if (el) el.src = "";
  refresh();
}

function kpi(cls, v, l) {
  return `<div class="kpi ${cls}"><div class="v">${v}</div><div class="l">${l}</div></div>`;
}

function renderKpis(s) {
  document.getElementById("kpis").innerHTML =
    kpi("b", s.total, "Cameras") + kpi("g", s.online, "Online") +
    kpi("r", s.offline, "Offline") + kpi("y", s.alerts, "Active alerts") +
    kpi("v", s.avg_trust, "Avg trust") + kpi("o", s.detections, "Live detections");
  const eb = document.getElementById("engineBadge");
  eb.textContent = "● YOLO " + s.detection_engine;
  eb.className = "engine " + (s.detection_engine === "ON" ? "on" : "off");
}

function trustColor(t) { return t >= 70 ? "#2fe08a" : t >= 40 ? "#ffd23f" : "#ff4d5e"; }

function renderCameras(cams) {
  const grid = document.getElementById("camGrid");
  if (!cams.length) {
    grid.innerHTML = `<div class="panel" style="grid-column:1/-1;text-align:center;color:var(--dim)">
      No cameras yet. Add a Pi stream link or the laptop webcam above.</div>`;
    return;
  }
  cams.forEach(c => {
    let card = document.getElementById("card-" + c.id);
    if (!card) {
      card = document.createElement("div");
      card.id = "card-" + c.id; card.className = "cam";
      card.innerHTML = `
        <button class="del" onclick="delCamera('${c.id}')">✕</button>
        <img class="feed" id="feed-${c.id}" src="/camera/${c.id}/video" alt="feed">
        <div class="bar"><div><span class="dot ${c.status}" id="dot-${c.id}"></span>
          <span class="nm">${c.name}</span><div class="src">${c.source}</div></div>
          <div class="trustring" id="trust-${c.id}"></div></div>
        <div class="stats" id="stats-${c.id}"></div>
        <div class="badges" id="badges-${c.id}"></div>
        <div class="labels" id="labels-${c.id}"></div>`;
      grid.appendChild(card);
    }
    card.className = "cam" + (c.alerts.length ? " alert" : "");
    document.getElementById("dot-" + c.id).className = "dot " + c.status;
    const tr = document.getElementById("trust-" + c.id);
    tr.textContent = c.trust + "%"; tr.style.color = trustColor(c.trust);
    document.getElementById("stats-" + c.id).innerHTML =
      `<div class="chip"><div class="cv" style="color:var(--blue)">${c.fps}</div><div class="cl">FPS</div></div>
       <div class="chip"><div class="cv" style="color:var(--yellow)">${c.det_count}</div><div class="cl">Objects</div></div>
       <div class="chip"><div class="cv" style="color:var(--green)">${c.latency_ms == null ? "—" : c.latency_ms + "ms"}</div><div class="cl">Latency</div></div>`;
    const b = document.getElementById("badges-" + c.id);
    b.innerHTML = c.alerts.length
      ? c.alerts.map(a => `<span class="badge red">⚠ ${a}</span>`).join("")
      : `<span class="badge green">✓ SECURE</span>`;
    const lbl = document.getElementById("labels-" + c.id);
    const parts = Object.entries(c.det_labels).map(([k, v]) => `${k}:<b>${v}</b>`);
    lbl.innerHTML = parts.length ? "Detected: " + parts.join("  ") : "";
  });
  // remove cards for deleted cameras
  [...grid.querySelectorAll(".cam")].forEach(card => {
    const id = card.id.replace("card-", "");
    if (!cams.find(c => c.id === id)) card.remove();
  });
}

function logAlerts(cams) {
  const log = document.getElementById("alertLog");
  cams.forEach(c => c.alerts.forEach(a => {
    const key = c.id + ":" + a + ":" + Math.floor(Date.now() / 5000);
    if (seenAlerts.has(key)) return;
    seenAlerts.add(key);
    if (log.querySelector(".empty")) log.innerHTML = "";
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `<span class="t">${new Date().toLocaleTimeString()}</span>
      &nbsp; <span class="c">${c.name}</span> &nbsp; <span class="a">${a}</span>`;
    log.prepend(row);
    while (log.children.length > 40) log.lastChild.remove();
  }));
}

function initCharts() {
  const base = {
    responsive: true, animation: false,
    plugins: { legend: { labels: { color: "#8ea2c9", font: { size: 10 } } } },
    scales: { x: { ticks: { color: "#8ea2c9", maxTicksLimit: 6 }, grid: { color: "#1e2b45" } },
              y: { ticks: { color: "#8ea2c9" }, grid: { color: "#1e2b45" }, beginAtZero: true } }
  };
  charts.trust = new Chart(document.getElementById("trustChart"),
    { type: "line", data: { labels: [], datasets: [] }, options: { ...base, scales: { ...base.scales, y: { ...base.scales.y, max: 100 } } } });
  charts.fps = new Chart(document.getElementById("fpsChart"),
    { type: "line", data: { labels: [], datasets: [] }, options: base });
  charts.det = new Chart(document.getElementById("detChart"),
    { type: "bar", data: { labels: [], datasets: [{ label: "Objects", data: [], backgroundColor: COLORS }] }, options: base });
  charts.health = new Chart(document.getElementById("healthChart"),
    { type: "bar", data: { labels: [], datasets: [
      { label: "Feed %", data: [], backgroundColor: "#2fe08a" },
      { label: "Network %", data: [], backgroundColor: "#3da5ff" } ] },
      options: { ...base, scales: { ...base.scales, y: { ...base.scales.y, max: 100 } } } });
}

function updateCharts(cams) {
  if (!charts.det) return;   // Chart.js unavailable
  const labels = cams.map(c => c.name);
  // bar charts
  charts.det.data.labels = labels;
  charts.det.data.datasets[0].data = cams.map(c => c.det_count);
  charts.det.update();
  charts.health.data.labels = labels;
  charts.health.data.datasets[0].data = cams.map(c => Math.round(c.feed_health * 100));
  charts.health.data.datasets[1].data = cams.map(c => Math.round(c.net_health * 100));
  charts.health.update();
  // time-series: use each camera's own history
  const maxLen = Math.max(1, ...cams.map(c => c.history.length));
  const axis = Array.from({ length: maxLen }, (_, i) => i);
  charts.trust.data.labels = axis;
  charts.fps.data.labels = axis;
  charts.trust.data.datasets = cams.map((c, i) => ({
    label: c.name, data: c.history.map(h => h.trust), borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + "22", tension: .35, pointRadius: 0, borderWidth: 2, fill: true }));
  charts.fps.data.datasets = cams.map((c, i) => ({
    label: c.name, data: c.history.map(h => h.fps), borderColor: COLORS[i % COLORS.length],
    tension: .35, pointRadius: 0, borderWidth: 2 }));
  charts.trust.update(); charts.fps.update();
}

async function refresh() {
  try {
    const r = await fetch("/api/cameras");
    const d = await r.json();
    renderKpis(d.summary);
    renderCameras(d.cameras);
    updateCharts(d.cameras);
    logAlerts(d.cameras);
  } catch (e) { console.error(e); }
}

try { if (window.Chart) initCharts(); else console.warn("Chart.js not loaded — graphs disabled"); }
catch (e) { console.error("chart init failed", e); }
refresh();
setInterval(refresh, 2000);
