"use strict";

// ---------------------------------------------------------------- 設定

const DATA_URL = "data/dashboard.json";
const RANGES = { "1M": 1, "3M": 3, "1Y": 12, "5Y": 60 }; // 月数
const MIN_POINTS = 12; // 月次データなど、期間が短いと点が足りないときは最低これだけ描く
const REFRESH_MS = 10 * 60 * 1000; // 開きっぱなしのタブもこの間隔でデータを読み直す
const STALE_HOURS = 3; // これより古いデータなら「更新が止まっている」と警告
const WEEKDAYS = "日月火水木金土";
const ARROWS = { 1: "▲", 0: "―", "-1": "▼" };

const state = { data: null, error: null, range: pref("range"), open: new Set() };
if (!(state.range in RANGES)) state.range = "1Y";

init();

function init() {
  for (const button of document.querySelectorAll(".range button")) {
    button.addEventListener("click", () => {
      state.range = button.dataset.range;
      pref("range", state.range);
      render();
    });
  }
  // 幅が変わったときだけ描き直す（スマホのスクロールで高さだけ変わるのは無視）
  let lastWidth = innerWidth;
  let timer;
  addEventListener("resize", () => {
    if (innerWidth === lastWidth) return;
    lastWidth = innerWidth;
    clearTimeout(timer);
    timer = setTimeout(render, 150);
  });
  load();
  setInterval(load, REFRESH_MS);
  setInterval(renderUpdated, 60 * 1000);
}

async function load() {
  try {
    const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();
    state.error = null;
  } catch (e) {
    state.error = e; // 前に読めたデータがあれば表示は続ける
  }
  render();
}

// ---------------------------------------------------------------- 描画

function render() {
  hideTip();
  for (const button of document.querySelectorAll(".range button")) {
    button.setAttribute("aria-pressed", String(button.dataset.range === state.range));
  }
  renderUpdated();

  const app = document.getElementById("app");
  if (!state.data) {
    const text = state.error ? `データを読み込めませんでした（${state.error.message}）` : "読み込み中…";
    app.replaceChildren(el("p", { class: "message" }, text));
    return;
  }
  const sections = new Map(); // section → indicators（初出順）
  for (const ind of state.data.indicators) {
    if (!sections.has(ind.section)) sections.set(ind.section, []);
    sections.get(ind.section).push(ind);
  }
  app.replaceChildren(...[...sections].map(([name, items]) => renderSection(name, items)));
  // 大きいチャートは表示幅が決まってから描く
  for (const box of app.querySelectorAll(".detail-chart")) drawDetail(box);
}

function renderUpdated() {
  const node = document.getElementById("updated");
  if (!state.data) {
    node.textContent = state.error ? "読み込み失敗" : "読み込み中…";
    return;
  }
  const at = new Date(state.data.generated_at);
  const mins = Math.max(0, Math.round((Date.now() - at) / 60000));
  const ago = mins < 60 ? `${mins}分前` : mins < 1440 ? `${Math.floor(mins / 60)}時間前` : `${Math.floor(mins / 1440)}日前`;
  const stale = mins > STALE_HOURS * 60;
  let text = `更新 ${fmtDateTime(at)}（${ago}）`;
  if (stale) text += " ⚠ 更新が止まっている可能性があります";
  if (state.error) text += " ⚠ 再読み込みに失敗";
  node.textContent = text;
  node.classList.toggle("stale", stale || Boolean(state.error));
}

function renderSection(name, items) {
  const groups = new Map(); // category → indicators（初出順）
  for (const ind of items) {
    if (!groups.has(ind.category)) groups.set(ind.category, []);
    groups.get(ind.category).push(ind);
  }
  const tbody = el("tbody");
  for (const [category, inds] of groups) {
    // 見出しと同じ小見出し（「雇用」カードの「雇用」など）は出さない
    if (category !== name) tbody.append(el("tr", { class: "cat" }, el("td", { colspan: 6 }, category)));
    for (const ind of inds) tbody.append(...renderRows(ind));
  }

  const head = el(
    "tr",
    {},
    el("th", {}, "指標"),
    el("th", {}, "現在値"),
    el("th", { class: "col-chg" }, "前回比"),
    el("th", { class: "col-period" }, `${state.range}変化`),
    el("th", {}, `推移 ${state.range}`),
    el("th", { class: "col-date" }, "日付"),
  );
  return el(
    "section",
    { class: "section" },
    el("h2", {}, name),
    el("table", {}, el("thead", {}, head), tbody),
  );
}

function renderRows(ind) {
  const open = state.open.has(ind.id);
  const nameCell = el("td", {}, el("button", { class: "name", type: "button", "aria-expanded": String(open) }, ind.name));
  if (ind.error) {
    const title = ind.series ? `取得に失敗したため前回のデータを表示しています\n${ind.error}` : ind.error;
    nameCell.append(el("span", { class: "badge", title }, "⚠"));
  }
  const row = el("tr", { class: "row" }, nameCell);
  row.addEventListener("click", () => toggle(ind, row));

  if (!ind.series) {
    row.append(el("td", { class: "na", colspan: 5 }, "取得できませんでした"));
    return open ? [row, detailRow(ind)] : [row];
  }

  const pts = windowOf(ind);
  const day = change(ind, ind.previous.value, ind.latest.value);
  const period = change(ind, pts[0].v, pts.at(-1).v);
  row.append(
    el(
      "td",
      {},
      el("span", { class: "value" }, fmtValue(ind, ind.latest.value)),
      // スマホでは前回比の列を畳んで、値の下に出す
      el("span", { class: `chg-inline ${dirClass(day.dir)}` }, `${ARROWS[day.dir]} ${day.text}`),
    ),
    changeCell(day),
    el("td", { class: `col-period ${dirClass(period.dir)}`, title: `${fmtDateLong(pts[0].d, ind.frequency)} 比` }, period.text),
    el("td", { class: "spark" }, chart(ind, pts, sparkSize())),
    el(
      "td",
      { class: "col-date date", title: fmtDateLong(ind.latest.date, ind.frequency) },
      fmtDateShort(ind.latest.date, ind.frequency),
    ),
  );
  return open ? [row, detailRow(ind)] : [row];
}

function changeCell(c) {
  const td = el("td", { class: `col-chg ${dirClass(c.dir)}` }, el("span", { class: "chg-main" }, `${ARROWS[c.dir]} ${c.text}`));
  if (c.sub) td.append(el("span", { class: "chg-sub" }, c.sub));
  return td;
}

function toggle(ind, row) {
  const open = !state.open.has(ind.id);
  if (open) state.open.add(ind.id);
  else state.open.delete(ind.id);
  row.querySelector(".name").setAttribute("aria-expanded", String(open));
  if (open) {
    const detail = detailRow(ind);
    row.after(detail);
    drawDetail(detail.querySelector(".detail-chart"));
  } else if (row.nextElementSibling?.classList.contains("detail")) {
    row.nextElementSibling.remove();
  }
}

function detailRow(ind) {
  const box = el("div", { class: "detail-chart", "data-id": ind.id });
  const meta = el("p", { class: "detail-meta" }, "出典: ");
  const href = /^https?:\/\//.test(ind.source_url) ? ind.source_url : "#";
  meta.append(el("a", { href, target: "_blank", rel: "noopener" }, `${ind.source} · ${ind.symbol}`));
  if (ind.fetched_at) meta.append(` · 最終取得 ${fmtDateTime(new Date(ind.fetched_at))}`);
  if (ind.note) meta.append(el("br"), ind.note);
  if (ind.error) meta.append(el("br"), el("span", { class: "err" }, `⚠ 直近の取得に失敗: ${ind.error}`));
  return el("tr", { class: "detail" }, el("td", { colspan: 6 }, box, meta));
}

function drawDetail(box) {
  const ind = state.data.indicators.find((i) => i.id === box.dataset.id);
  if (!ind?.series || !box.clientWidth) return;
  box.replaceChildren(chart(ind, windowOf(ind), { width: box.clientWidth, height: 220, axes: true }));
}

function sparkSize() {
  return matchMedia("(max-width: 640px)").matches ? { width: 88, height: 30 } : { width: 124, height: 34 };
}

// ---------------------------------------------------------------- チャート（SVG 手書き）

function chart(ind, pts, { width: W, height: H, axes = false }) {
  const n = pts.length;
  const pad = axes ? { l: 4, r: 58, t: 10, b: 24 } : { l: 2, r: 4, t: 4, b: 4 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const values = pts.map((p) => p.v);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  let ticks = [];
  let tickDecimals = 0;
  if (axes) {
    ({ ticks, decimals: tickDecimals } = niceTicks(lo, hi, 5));
    lo = ticks[0];
    hi = ticks.at(-1);
  } else {
    const margin = (hi - lo) * 0.08 || Math.abs(hi) * 0.001 || 1;
    lo -= margin;
    hi += margin;
  }
  const X = (i) => pad.l + (n > 1 ? (iw * i) / (n - 1) : iw);
  const Y = (v) => pad.t + ih * (1 - (v - lo) / (hi - lo));

  const svg = svgEl("svg", {
    width: W,
    height: H,
    viewBox: `0 0 ${W} ${H}`,
    class: axes ? "chart" : "sparkline",
    role: "img",
    "aria-label": `${ind.name} ${fmtDateLong(pts[0].d, ind.frequency)}〜${fmtDateLong(pts.at(-1).d, ind.frequency)}`,
  });

  if (axes) {
    for (const t of ticks) {
      svg.append(svgEl("line", { class: "c-grid", x1: pad.l, x2: W - pad.r, y1: Y(t), y2: Y(t) }));
      svg.append(svgText(nf(tickDecimals).format(t), { x: W - pad.r + 6, y: Y(t) + 4 }));
    }
    const spanDays = (parseDate(pts.at(-1).d) - parseDate(pts[0].d)) / 864e5;
    const labels = Math.min(n, W < 420 ? 3 : 5);
    for (let k = 0; k < labels; k++) {
      const i = Math.round((k * (n - 1)) / (labels - 1));
      const anchor = k === 0 ? "start" : k === labels - 1 ? "end" : "middle";
      svg.append(svgText(fmtAxisDate(pts[i].d, spanDays, ind.frequency), { x: X(i), y: H - 6, "text-anchor": anchor }));
    }
  } else {
    // 期間の始値の水準（そこより上か下かが一目で分かる）
    svg.append(svgEl("line", { class: "c-ref", x1: pad.l, x2: W - pad.r, y1: Y(pts[0].v), y2: Y(pts[0].v) }));
  }

  const line = pts.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.v).toFixed(1)}`).join("");
  const base = (H - pad.b).toFixed(1);
  svg.append(svgEl("path", { class: "c-area", d: `${line}L${X(n - 1).toFixed(1)},${base}L${X(0).toFixed(1)},${base}Z` }));
  svg.append(svgEl("path", { class: "c-line", d: line }));
  svg.append(svgEl("circle", { class: "c-dot", cx: X(n - 1), cy: Y(pts[n - 1].v), r: axes ? 3.5 : 2.5 }));

  // ホバー: 縦線が最寄りの日付に吸い付き、値と日付をツールチップに出す
  const cross = svgEl("line", { class: "c-cross", y1: pad.t, y2: H - pad.b, visibility: "hidden" });
  const dot = svgEl("circle", { class: "c-dot", r: axes ? 4.5 : 3, visibility: "hidden" });
  const hit = svgEl("rect", { class: "c-hit", x: 0, y: 0, width: W, height: H });
  svg.append(cross, dot, hit);
  hit.addEventListener("pointermove", (ev) => {
    const box = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(n - 1, Math.round(((ev.clientX - box.left - pad.l) / iw) * (n - 1))));
    const x = X(i);
    const y = Y(pts[i].v);
    for (const [k, v] of [["x1", x], ["x2", x]]) cross.setAttribute(k, v);
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", y);
    cross.setAttribute("visibility", "visible");
    dot.setAttribute("visibility", "visible");
    showTip(box.left + x, box.top + y, fmtValue(ind, pts[i].v), fmtDateLong(pts[i].d, ind.frequency));
  });
  hit.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    hideTip();
  });
  return svg;
}

function niceTicks(lo, hi, count) {
  if (hi - lo < 1e-9) {
    const m = Math.abs(hi) * 0.01 || 1;
    lo -= m;
    hi += m;
  }
  const raw = (hi - lo) / (count - 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw * (1 - 1e-9));
  const first = Math.floor(lo / step) * step;
  const last = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let k = 0; first + k * step <= last + step * 1e-6; k++) ticks.push(Number((first + k * step).toPrecision(12)));
  let decimals = 0;
  while (decimals < 6 && Math.abs(step * 10 ** decimals - Math.round(step * 10 ** decimals)) > 1e-6) decimals++;
  return { ticks, decimals };
}

function showTip(x, y, value, label) {
  const tip = document.getElementById("tip");
  tip.querySelector("strong").textContent = value;
  tip.querySelector("span").textContent = label;
  tip.hidden = false;
  const w = tip.offsetWidth;
  tip.classList.toggle("below", y - tip.offsetHeight - 12 < 0);
  tip.style.left = `${Math.max(w / 2 + 4, Math.min(innerWidth - w / 2 - 4, x))}px`;
  tip.style.top = `${y}px`;
}

function hideTip() {
  document.getElementById("tip").hidden = true;
}

// ---------------------------------------------------------------- データの加工

/** 選択中の期間ぶんの点を返す（点が少なすぎるときは MIN_POINTS まで遡る） */
function windowOf(ind) {
  const { dates, values } = ind.series;
  const cutoff = shiftMonths(dates.at(-1), -RANGES[state.range]);
  let i = dates.findIndex((d) => d >= cutoff);
  i = Math.max(0, Math.min(i, dates.length - MIN_POINTS));
  return dates.slice(i).map((d, k) => ({ d, v: values[i + k] }));
}

/** from → to の変化を indicators.toml の change 設定に従って文字にする */
function change(ind, from, to) {
  const d = to - from;
  if (ind.change === "bp") {
    const s = signed(d * 100, Math.max(0, ind.decimals - 2));
    return { dir: s.sign, text: `${s.text}bp` };
  }
  if (ind.change === "diff") {
    const s = signed(d, ind.decimals);
    return { dir: s.sign, text: s.text + (ind.unit === "%" ? "pt" : ind.unit) };
  }
  const abs = signed(d, ind.decimals);
  const pct = signed(from ? (d / from) * 100 : 0, 2);
  return { dir: abs.sign, text: `${pct.text}%`, sub: abs.text };
}

function signed(x, decimals) {
  const r = Number(x.toFixed(decimals));
  const sign = Math.sign(r) || 0;
  return { sign, text: (sign > 0 ? "+" : sign < 0 ? "−" : "±") + nf(decimals).format(Math.abs(r)) };
}

function dirClass(dir) {
  return dir > 0 ? "up" : dir < 0 ? "down" : "flat";
}

// ---------------------------------------------------------------- 書式

const numberFormats = new Map();
function nf(decimals) {
  if (!numberFormats.has(decimals)) {
    numberFormats.set(
      decimals,
      new Intl.NumberFormat("ja-JP", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }),
    );
  }
  return numberFormats.get(decimals);
}

function fmtValue(ind, v) {
  return nf(ind.decimals).format(v) + (ind.unit || "");
}

const dateTimeFormat = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
function fmtDateTime(date) {
  return dateTimeFormat.format(date);
}

function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function shiftMonths(iso, months) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1 + months, d)).toISOString().slice(0, 10);
}

function fmtDateShort(iso, frequency) {
  const t = parseDate(iso);
  if (frequency === "monthly") return `${t.getFullYear()}年${t.getMonth() + 1}月`;
  return `${t.getMonth() + 1}/${t.getDate()} (${WEEKDAYS[t.getDay()]})`;
}

function fmtDateLong(iso, frequency) {
  const t = parseDate(iso);
  if (frequency === "monthly") return `${t.getFullYear()}年${t.getMonth() + 1}月`;
  return `${t.getFullYear()}/${t.getMonth() + 1}/${t.getDate()} (${WEEKDAYS[t.getDay()]})`;
}

function fmtAxisDate(iso, spanDays, frequency) {
  const t = parseDate(iso);
  if (frequency === "monthly" || spanDays > 200) return `${t.getFullYear()}/${String(t.getMonth() + 1).padStart(2, "0")}`;
  return `${t.getMonth() + 1}/${t.getDate()}`;
}

// ---------------------------------------------------------------- DOM ヘルパー

/** 子に渡した文字列はテキストノードになる（innerHTML は使わない） */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  node.append(...children);
  return node;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function svgText(text, attrs) {
  const node = svgEl("text", attrs);
  node.textContent = text;
  return node;
}

function pref(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch {
    return null; // プライベートモード等では保存しない
  }
}
