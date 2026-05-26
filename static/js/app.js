// ── Constants ──────────────────────────────────────────────────────────────

const COLOURS = { p1: "#3b82f6", p2: "#f97316" };

const STAT_LABELS = {
  total_points:                 "Total Points",
  goals_scored:                 "Goals Scored",
  assists:                      "Assists",
  clean_sheets:                 "Clean Sheets",
  goals_conceded:               "Goals Conceded",
  own_goals:                    "Own Goals",
  saves:                        "Saves",
  penalties_saved:              "Penalties Saved",
  penalties_missed:             "Penalties Missed",
  bonus:                        "Bonus Points",
  bps:                          "BPS",
  minutes:                      "Minutes Played",
  expected_goals:               "xG",
  expected_assists:             "xA",
  expected_goal_involvements:   "xGI",
  expected_goals_conceded:      "xGC",
  influence:                    "Influence",
  creativity:                   "Creativity",
  threat:                       "Threat",
  ict_index:                    "ICT Index",
  selected:                     "Selected By",
  transfers_in:                 "Transfers In",
  transfers_out:                "Transfers Out",
  transfers_balance:            "Net Transfers",
};

const STAT_GROUPS = [
  { label: "Performance", stats: ["total_points", "goals_scored", "assists", "clean_sheets", "bonus", "bps"] },
  { label: "Involvement", stats: ["minutes", "saves", "goals_conceded", "own_goals", "penalties_saved", "penalties_missed"] },
  { label: "Expected",    stats: ["expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded"] },
  { label: "ICT",         stats: ["influence", "creativity", "threat", "ict_index"] },
  { label: "Transfers",   stats: ["selected", "transfers_in", "transfers_out", "transfers_balance"] },
];

// ── State ──────────────────────────────────────────────────────────────────

const state = {
  players: [],
  seasons: [],
  season:  "current",
  p1: null, p2: null,
  h1: [],   h2: [],
  f1: [],   f2: [],
  stat:   "total_points",
  gwFrom: 1,
  gwTo:   38,
};

// ── Security helpers ───────────────────────────────────────────────────────

const _escapeEl = document.createElement("span");
function escapeHTML(str) {
  _escapeEl.textContent = String(str);
  return _escapeEl.innerHTML;
}

// Clamp FDR difficulty to 1–5 so it can safely be used as a CSS class suffix.
function safeFdr(difficulty) {
  const n = parseInt(difficulty, 10);
  return (n >= 1 && n <= 5) ? n : 3;
}

// ── API ────────────────────────────────────────────────────────────────────

async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} from ${path}`);
  return res.json();
}

function playersUrl() {
  return state.season === "current"
    ? "/api/players"
    : `/api/players?season=${encodeURIComponent(state.season)}`;
}

function historyUrl(playerId) {
  return state.season === "current"
    ? `/api/player/${playerId}/history`
    : `/api/player/${playerId}/history?season=${encodeURIComponent(state.season)}`;
}

function fixturesUrl(playerId) {
  return state.season === "current"
    ? `/api/player/${playerId}/fixtures`
    : `/api/player/${playerId}/fixtures?season=${encodeURIComponent(state.season)}`;
}

// ── URL management ─────────────────────────────────────────────────────────

function updateURL() {
  const params = new URLSearchParams();
  if (state.season !== "current")       params.set("season", state.season);
  if (state.p1)                          params.set("p1", state.p1.id);
  if (state.p2)                          params.set("p2", state.p2.id);
  if (state.stat !== "total_points")    params.set("stat", state.stat);
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : "/");
}

// ── Share button ───────────────────────────────────────────────────────────

function initShareButton() {
  document.getElementById("share-btn").addEventListener("click", () => {
    const url = window.location.href;
    const label = document.getElementById("share-btn-label");

    const reset = () => { label.textContent = "Copy link"; };

    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() => {
        label.textContent = "Copied!";
        setTimeout(reset, 2000);
      }).catch(() => fallbackCopy(url, label, reset));
    } else {
      fallbackCopy(url, label, reset);
    }
  });
}

function fallbackCopy(url, label, reset) {
  const ta = document.createElement("textarea");
  ta.value = url;
  ta.style.cssText = "position:fixed;opacity:0;pointer-events:none";
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
    label.textContent = "Copied!";
  } catch {
    label.textContent = "Copy failed";
  }
  document.body.removeChild(ta);
  setTimeout(reset, 2000);
}

// ── Season selector ────────────────────────────────────────────────────────

async function loadSeasons() {
  try {
    state.seasons = await apiFetch("/api/seasons");
  } catch {
    state.seasons = [{ id: "current", label: "Live" }];
  }
  const select = document.getElementById("season-select");
  state.seasons.forEach(s => {
    const opt = document.createElement("option");
    opt.value       = s.id;
    opt.textContent = s.label;
    if (s.id === state.season) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener("change", () => changeSeason(select.value));
}

async function changeSeason(newSeason) {
  if (newSeason === state.season) return;
  state.season = newSeason;

  // Clear existing player selections
  state.p1 = null; state.p2 = null;
  state.h1 = []; state.h2 = [];
  state.f1 = []; state.f2 = [];
  document.getElementById("search1").value = "";
  document.getElementById("search2").value = "";
  renderCard(null, 1);
  renderCard(null, 2);
  maybeShowCharts();
  updateURL();

  try {
    state.players = await apiFetch(playersUrl());
  } catch (err) {
    console.error("Failed to load players for season:", err);
    state.players = [];
  }
}

// ── Search / Autocomplete ──────────────────────────────────────────────────

function buildSearch(num) {
  const input    = document.getElementById(`search${num}`);
  const dropdown = document.getElementById(`dropdown${num}`);
  let activeIdx  = -1;

  function showDropdown(items) {
    dropdown.innerHTML = "";
    activeIdx = -1;
    items.forEach((p) => {
      const el = document.createElement("div");
      el.className = "fpl-dropdown-item";
      el.innerHTML = `
        <span>${escapeHTML(p.full_name)}</span>
        <span class="meta">${escapeHTML(p.team)} &middot; ${escapeHTML(p.position)} &middot; &pound;${p.now_cost}m</span>
      `;
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        confirmSelection(p);
      });
      dropdown.appendChild(el);
    });
    dropdown.classList.toggle("hidden", items.length === 0);
  }

  function confirmSelection(p) {
    input.value = p.full_name;
    dropdown.classList.add("hidden");
    selectPlayer(num, p);
  }

  function clearPlayer() {
    if (num === 1) { state.p1 = null; state.h1 = []; state.f1 = []; }
    else           { state.p2 = null; state.h2 = []; state.f2 = []; }
    renderCard(null, num);
    updateURL();
    maybeShowCharts();
  }

  input.addEventListener("input", () => {
    const q = input.value.trim();
    if (!q) { dropdown.classList.add("hidden"); clearPlayer(); return; }
    if (q.length < 2) { dropdown.classList.add("hidden"); return; }

    const matches = state.players
      .filter(p =>
        p.full_name.toLowerCase().includes(q.toLowerCase()) ||
        p.team.toLowerCase().includes(q.toLowerCase())
      )
      .slice(0, 10);
    showDropdown(matches);
  });

  input.addEventListener("keydown", (e) => {
    const items = dropdown.querySelectorAll(".fpl-dropdown-item");
    if (!items.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
    } else if (e.key === "Enter" && activeIdx >= 0) {
      items[activeIdx].dispatchEvent(new MouseEvent("mousedown"));
      return;
    } else if (e.key === "Escape") {
      dropdown.classList.add("hidden");
      return;
    }
    items.forEach((el, i) => el.classList.toggle("active", i === activeIdx));
  });

  input.addEventListener("blur", () => {
    setTimeout(() => dropdown.classList.add("hidden"), 150);
  });
}

// ── Player card ────────────────────────────────────────────────────────────

function renderCard(player, num) {
  const card = document.getElementById(`card${num}`);
  if (!player) { card.classList.add("hidden"); return; }

  card.innerHTML = `
    <div class="flex items-start justify-between">
      <div>
        <div class="text-base font-bold text-white">${escapeHTML(player.full_name)}</div>
        <div class="text-xs text-slate-400 mt-1">${escapeHTML(player.team)} &middot; ${escapeHTML(player.position)}</div>
      </div>
      <div class="text-right">
        <div class="text-lg font-bold text-white">&pound;${player.now_cost}m</div>
        <div class="text-xs text-slate-400 mt-1">${escapeHTML(player.selected_by_percent)}% owned</div>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-2 mt-4">
      <div class="bg-slate-800 rounded-lg p-2 text-center">
        <div class="text-sm font-bold text-white">${player.total_points}</div>
        <div class="text-xs text-slate-500">pts</div>
      </div>
      <div class="bg-slate-800 rounded-lg p-2 text-center">
        <div class="text-sm font-bold text-white">${escapeHTML(player.form)}</div>
        <div class="text-xs text-slate-500">form</div>
      </div>
    </div>
  `;
  card.classList.remove("hidden");
}

// ── Bar chart ──────────────────────────────────────────────────────────────

function renderBarChart(h1, h2, p1, p2, stat) {
  const container = document.getElementById("bar-chart");
  container.innerHTML = "";

  const W = 800, H = 296;
  const margin = { top: 16, right: 24, bottom: 56, left: 48 };
  const width  = W - margin.left - margin.right;
  const height = H - margin.top  - margin.bottom;

  const rounds = [...new Set([...h1.map(d => d.round), ...h2.map(d => d.round)])].sort((a, b) => a - b);
  const idx1 = Object.fromEntries(h1.map(d => [d.round, d[stat] ?? 0]));
  const idx2 = Object.fromEntries(h2.map(d => [d.round, d[stat] ?? 0]));
  const data  = rounds.map(r => ({ round: r, p1: idx1[r] ?? 0, p2: idx2[r] ?? 0 }));

  const svg = d3.select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${W} ${H}`)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("width", "100%")
    .style("height", "auto");

  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const xOuter = d3.scaleBand().domain(rounds).range([0, width]).paddingInner(0.25);
  const xInner = d3.scaleBand().domain(["p1", "p2"]).range([0, xOuter.bandwidth()]).padding(0.06);
  const maxVal  = Math.max(d3.max(data, d => Math.max(d.p1, d.p2)) ?? 0, 1);
  const y = d3.scaleLinear().domain([0, maxVal]).range([height, 0]).nice();

  g.append("g").attr("class", "chart-grid")
    .selectAll("line")
    .data(y.ticks(5))
    .join("line")
    .attr("x1", 0).attr("x2", width)
    .attr("y1", d => y(d)).attr("y2", d => y(d));

  g.selectAll(".bar-p1").data(data).join("rect")
    .attr("class", "bar-p1")
    .attr("x",      d => xOuter(d.round) + xInner("p1"))
    .attr("y",      d => y(d.p1))
    .attr("width",  xInner.bandwidth())
    .attr("height", d => height - y(d.p1))
    .attr("fill",   COLOURS.p1)
    .attr("rx", 2);

  g.selectAll(".bar-p2").data(data).join("rect")
    .attr("class", "bar-p2")
    .attr("x",      d => xOuter(d.round) + xInner("p2"))
    .attr("y",      d => y(d.p2))
    .attr("width",  xInner.bandwidth())
    .attr("height", d => height - y(d.p2))
    .attr("fill",   COLOURS.p2)
    .attr("rx", 2);

  const step = rounds.length > 20 ? 5 : rounds.length > 10 ? 2 : 1;
  g.append("g").attr("class", "chart-axis")
    .attr("transform", `translate(0,${height})`)
    .call(
      d3.axisBottom(xOuter)
        .tickValues(rounds.filter((_, i) => i % step === 0))
        .tickSize(4)
        .tickPadding(6)
    );

  g.append("g").attr("class", "chart-axis")
    .call(d3.axisLeft(y).ticks(5).tickSize(4).tickPadding(6));

  const legend = svg.append("g")
    .attr("transform", `translate(${margin.left},${H - 28})`);

  [[p1, COLOURS.p1], [p2, COLOURS.p2]].forEach(([p, colour], i) => {
    const ly = i * 14;
    legend.append("rect")
      .attr("x", 0).attr("y", ly)
      .attr("width", 10).attr("height", 10)
      .attr("fill", colour).attr("rx", 2);
    legend.append("text")
      .attr("x", 14).attr("y", ly + 9)
      .attr("fill", "#94a3b8").attr("font-size", 11)
      .text(p.full_name.length > 30 ? p.full_name.slice(0, 30) + "…" : p.full_name);
  });

  const tooltip = d3.select(".fpl-tooltip");
  svg.on("mousemove", function (event) {
    const [mx] = d3.pointer(event, g.node());
    const round = rounds[Math.max(0, Math.floor(mx / xOuter.step()))];
    const d = data.find(x => x.round === round);
    if (!d) { tooltip.style("display", "none"); return; }
    const label = STAT_LABELS[stat] || stat;
    tooltip
      .style("display", "block")
      .style("left", event.clientX + 14 + "px")
      .style("top",  event.clientY - 36 + "px")
      .html(`
        <div style="color:#94a3b8;margin-bottom:4px">GW ${round} &mdash; ${label}</div>
        <div style="color:${COLOURS.p1}">${p1.full_name.split(" ").pop()}: <strong>${d.p1}</strong></div>
        <div style="color:${COLOURS.p2}">${p2.full_name.split(" ").pop()}: <strong>${d.p2}</strong></div>
      `);
  }).on("mouseleave", () => tooltip.style("display", "none"));
}

// ── Line chart (cumulative) ────────────────────────────────────────────────

function renderLineChart(h1, h2, p1, p2, stat) {
  const container = document.getElementById("line-chart");
  container.innerHTML = "";

  const W = 800, H = 260;
  const margin = { top: 16, right: 24, bottom: 40, left: 56 };
  const width  = W - margin.left - margin.right;
  const height = H - margin.top  - margin.bottom;

  function cumulative(history) {
    let sum = 0;
    return history.map(d => ({ round: d.round, value: (sum += d[stat] ?? 0) }));
  }

  const c1     = cumulative(h1);
  const c2     = cumulative(h2);
  const rounds = [...new Set([...c1.map(d => d.round), ...c2.map(d => d.round)])].sort((a, b) => a - b);

  const x    = d3.scaleLinear().domain([rounds[0] ?? 1, rounds[rounds.length - 1] ?? 1]).range([0, width]);
  const maxY = Math.max(d3.max(c1, d => d.value) ?? 0, d3.max(c2, d => d.value) ?? 0, 1);
  const y    = d3.scaleLinear().domain([0, maxY]).range([height, 0]).nice();

  const lineGen = d3.line()
    .x(d => x(d.round))
    .y(d => y(d.value))
    .curve(d3.curveMonotoneX);

  const svg = d3.select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${W} ${H}`)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("width", "100%")
    .style("height", "auto");

  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  g.append("g").attr("class", "chart-grid")
    .selectAll("line")
    .data(y.ticks(5))
    .join("line")
    .attr("x1", 0).attr("x2", width)
    .attr("y1", d => y(d)).attr("y2", d => y(d));

  [[c1, COLOURS.p1, p1], [c2, COLOURS.p2, p2]].forEach(([data, colour]) => {
    if (!data.length) return;

    g.append("path")
      .datum(data)
      .attr("fill",         "none")
      .attr("stroke",       colour)
      .attr("stroke-width", 2.5)
      .attr("d",            lineGen);

    const last = data[data.length - 1];
    g.append("circle")
      .attr("cx", x(last.round)).attr("cy", y(last.value))
      .attr("r", 4).attr("fill", colour);
  });

  const step = rounds.length > 20 ? 5 : rounds.length > 10 ? 2 : 1;
  g.append("g").attr("class", "chart-axis")
    .attr("transform", `translate(0,${height})`)
    .call(
      d3.axisBottom(x)
        .tickValues(rounds.filter((_, i) => i % step === 0))
        .tickFormat(d => `GW${d}`)
        .tickSize(4).tickPadding(6)
    );

  g.append("g").attr("class", "chart-axis")
    .call(d3.axisLeft(y).ticks(5).tickSize(4).tickPadding(6));
}

// ── Fixtures ───────────────────────────────────────────────────────────────

function renderFixtures(fixtures, containerId, playerName, titleId) {
  document.getElementById(titleId).textContent = playerName;

  const el = document.getElementById(containerId);
  if (!fixtures.length) {
    el.innerHTML = `<p class="text-slate-600 text-sm">No upcoming fixtures</p>`;
    return;
  }

  el.innerHTML = fixtures.slice(0, 8).map(f => {
    const opponent = escapeHTML(f.is_home ? f.team_a : f.team_h);
    const venue    = f.is_home ? "H" : "A";
    const fdr      = safeFdr(f.difficulty);
    return `
      <div class="flex items-center gap-3">
        <span class="text-xs text-slate-500 w-10 shrink-0">GW&nbsp;${parseInt(f.event, 10)}</span>
        <span class="fdr-${fdr} rounded px-2 py-1 text-xs font-bold w-10 text-center shrink-0">${opponent}</span>
        <span class="text-xs font-semibold ${f.is_home ? "text-slate-300" : "text-slate-500"}">${venue}</span>
        <div class="flex-1 h-1.5 rounded-full fdr-${fdr} opacity-30"></div>
      </div>
    `;
  }).join("");
}

// ── Stat selector ──────────────────────────────────────────────────────────

function initStatSelector() {
  const select = document.getElementById("stat-select");

  STAT_GROUPS.forEach(group => {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.label;
    group.stats.forEach(s => {
      const opt = document.createElement("option");
      opt.value       = s;
      opt.textContent = STAT_LABELS[s] || s;
      if (s === state.stat) opt.selected = true;
      optgroup.appendChild(opt);
    });
    select.appendChild(optgroup);
  });

  select.addEventListener("change", () => {
    state.stat = select.value;
    if (state.h1.length && state.h2.length) {
      refreshCharts();
      updateURL();
    }
  });
}

// ── GW range ───────────────────────────────────────────────────────────────

function initGwRange() {
  const fromEl = document.getElementById("gw-from");
  const toEl   = document.getElementById("gw-to");

  function apply() {
    const from = Math.max(1, parseInt(fromEl.value) || 1);
    const to   = Math.min(parseInt(toEl.value) || 38, parseInt(toEl.max) || 38);
    if (from > to) return;
    state.gwFrom = from;
    state.gwTo   = to;
    if (state.h1.length && state.h2.length) refreshCharts();
  }

  fromEl.addEventListener("change", apply);
  toEl.addEventListener("change", apply);
}

function setGwRangeFromData() {
  const allRounds = [...state.h1, ...state.h2].map(d => d.round);
  if (!allRounds.length) return;
  const minGw = Math.min(...allRounds);
  const maxGw = Math.max(...allRounds);

  const fromEl = document.getElementById("gw-from");
  const toEl   = document.getElementById("gw-to");
  fromEl.min = minGw; fromEl.max = maxGw; fromEl.value = minGw;
  toEl.min   = minGw; toEl.max   = maxGw; toEl.value   = maxGw;
  state.gwFrom = minGw;
  state.gwTo   = maxGw;
}

// ── Orchestration ──────────────────────────────────────────────────────────

async function selectPlayer(num, player) {
  if (num === 1) state.p1 = player;
  else           state.p2 = player;
  renderCard(player, num);

  const [history, fixtures] = await Promise.all([
    apiFetch(historyUrl(player.id)).catch(err => {
      console.error(`History fetch failed for player ${player.id}:`, err);
      return [];
    }),
    apiFetch(fixturesUrl(player.id)).catch(err => {
      console.error(`Fixtures fetch failed for player ${player.id}:`, err);
      return [];
    }),
  ]);

  if (num === 1) { state.h1 = history; state.f1 = fixtures; }
  else           { state.h2 = history; state.f2 = fixtures; }

  updateURL();
  maybeShowCharts();
}

function refreshCharts() {
  const { h1, h2, f1, f2, p1, p2, stat, gwFrom, gwTo } = state;
  const fh1 = h1.filter(d => d.round >= gwFrom && d.round <= gwTo);
  const fh2 = h2.filter(d => d.round >= gwFrom && d.round <= gwTo);
  renderBarChart(fh1, fh2, p1, p2, stat);
  renderLineChart(fh1, fh2, p1, p2, stat);
  renderFixtures(f1, "fixtures1", p1.full_name, "fixtures1-title");
  renderFixtures(f2, "fixtures2", p2.full_name, "fixtures2-title");
}

function maybeShowCharts() {
  const ready = state.p1 && state.p2 && state.h1.length && state.h2.length;
  document.getElementById("empty-state").classList.toggle("hidden", ready);
  document.getElementById("charts-section").classList.toggle("hidden", !ready);
  document.getElementById("share-btn").classList.toggle("hidden", !ready);
  document.getElementById("share-btn").classList.toggle("flex", ready);
  if (ready) {
    setGwRangeFromData();
    refreshCharts();
  }
}

// ── Init ───────────────────────────────────────────────────────────────────

async function init() {
  initStatSelector();
  initGwRange();
  initShareButton();

  // Load available seasons and build the selector.
  await loadSeasons();

  // Restore state from URL params before fetching players.
  const params = new URLSearchParams(window.location.search);

  const urlSeason = params.get("season");
  if (urlSeason && state.seasons.find(s => s.id === urlSeason)) {
    state.season = urlSeason;
    document.getElementById("season-select").value = urlSeason;
  }

  const urlStat = params.get("stat");
  if (urlStat && Object.keys(STAT_LABELS).includes(urlStat)) {
    state.stat = urlStat;
    document.getElementById("stat-select").value = urlStat;
  }

  // Fetch the player roster for the selected season.
  try {
    state.players = await apiFetch(playersUrl());
  } catch (err) {
    console.error("Failed to load players:", err);
    const el = document.getElementById("empty-state");
    el.textContent = "Could not load player data. Make sure the server is running.";
    el.classList.remove("hidden");
    return;
  }

  buildSearch(1);
  buildSearch(2);

  // Auto-select players from URL (e.g. from a shared link).
  const p1id = params.get("p1");
  const p2id = params.get("p2");
  const autoSelects = [];

  if (p1id) {
    const p = state.players.find(p => String(p.id) === p1id);
    if (p) {
      document.getElementById("search1").value = p.full_name;
      autoSelects.push(selectPlayer(1, p));
    }
  }
  if (p2id) {
    const p = state.players.find(p => String(p.id) === p2id);
    if (p) {
      document.getElementById("search2").value = p.full_name;
      autoSelects.push(selectPlayer(2, p));
    }
  }
  await Promise.all(autoSelects);
}

document.addEventListener("DOMContentLoaded", init);
