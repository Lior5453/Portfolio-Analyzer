// Investment portfolio - holdings entry and allocation chart
const STORAGE_KEY = "portfolio-holdings";
const MAX_SLICES = 8; // beyond this, the smallest assets are grouped into "Other"

const state = {
  holdings: load(),
  groupBy: "name",
  editingId: null,
};

const $ = (sel) => document.querySelector(sel);
const form = $("#holding-form");
const tbody = $("#holdings-table tbody");
const svg = $("#donut");
const tooltip = $("#tooltip");

const money = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 0 });
const money2 = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 2 });
const number = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 4 });
const pct = (v) => (v * 100).toFixed(1) + "%";

function load() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
  catch { return []; }
}
function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.holdings)); } catch {}
}

const valueOf = (h) => h.quantity * h.price;
const total = () => state.holdings.reduce((s, h) => s + valueOf(h), 0);

// ---------- Form ----------
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const data = new FormData(form);
  const holding = {
    id: state.editingId || crypto.randomUUID(),
    name: data.get("name").trim().toUpperCase(),
    type: data.get("type"),
    quantity: parseFloat(data.get("quantity")),
    price: parseFloat(data.get("price")),
  };
  if (!holding.name || !(holding.quantity >= 0) || !(holding.price >= 0)) return;

  if (state.editingId) {
    state.holdings = state.holdings.map((h) => (h.id === state.editingId ? holding : h));
  } else {
    state.holdings.push(holding);
  }
  resetForm();
  save();
  render();
});

$("#cancel-edit").addEventListener("click", resetForm);

// ---------- Automatic market price ----------
const quoteStatus = $("#quote-status");
let quoteTimer = null;
let quoteSeq = 0; // ignore stale responses if the user kept typing

function setQuoteStatus(text, kind = "") {
  quoteStatus.textContent = text;
  quoteStatus.className = "quote-status" + (kind ? " " + kind : "");
}

async function lookupPrice() {
  const symbol = form.name.value.trim();
  const seq = ++quoteSeq;
  form.price.classList.remove("auto-filled");
  if (!symbol) { setQuoteStatus(""); return; }

  setQuoteStatus("מחפש מחיר עדכני…");
  try {
    const res = await fetch(`/api/quote?symbol=${encodeURIComponent(symbol)}`);
    if (seq !== quoteSeq) return;
    if (res.status === 404) { setQuoteStatus("לא נמצא נכס בסימול הזה – אפשר להזין מחיר ידנית", "error"); return; }
    if (!res.ok) throw new Error();
    const q = await res.json();
    if (seq !== quoteSeq) return;

    form.price.value = +q.priceILS.toFixed(2);
    form.price.classList.add("auto-filled");
    const original = q.currency === "ILS" ? "" :
      ` (${new Intl.NumberFormat("he-IL", { style: "currency", currency: q.currency }).format(q.price)})`;
    setQuoteStatus(`${q.name}: ${money2.format(q.priceILS)}${original}`, "ok");
  } catch {
    if (seq === quoteSeq) setQuoteStatus("לא הצלחתי למשוך מחיר כרגע – אפשר להזין ידנית", "error");
  }
}

form.name.addEventListener("input", () => {
  clearTimeout(quoteTimer);
  quoteTimer = setTimeout(lookupPrice, 700);
});
form.name.addEventListener("blur", () => {
  if (quoteTimer) { clearTimeout(quoteTimer); quoteTimer = null; lookupPrice(); }
});
form.price.addEventListener("input", () => form.price.classList.remove("auto-filled"));

function resetForm() {
  form.reset();
  clearTimeout(quoteTimer);
  quoteTimer = null;
  quoteSeq++;
  setQuoteStatus("");
  form.price.classList.remove("auto-filled");
  state.editingId = null;
  $("#submit-btn").textContent = "הוסף לתיק";
  $("#cancel-edit").hidden = true;
}

function startEdit(id) {
  const h = state.holdings.find((x) => x.id === id);
  if (!h) return;
  state.editingId = id;
  form.name.value = h.name;
  form.type.value = h.type;
  form.quantity.value = h.quantity;
  form.price.value = h.price;
  $("#submit-btn").textContent = "שמור שינויים";
  $("#cancel-edit").hidden = false;
  form.name.focus();
}

function remove(id) {
  state.holdings = state.holdings.filter((h) => h.id !== id);
  if (state.editingId === id) resetForm();
  save();
  render();
}

// ---------- Chart grouping ----------
// Color is tied to the entity (name/type) by insertion order, so it stays stable when values change
function slices() {
  const key = state.groupBy;
  const order = [];
  const sums = new Map();
  for (const h of state.holdings) {
    const k = h[key];
    if (!sums.has(k)) { sums.set(k, 0); order.push(k); }
    sums.set(k, sums.get(k) + valueOf(h));
  }
  const sum = total();
  let items = order.map((label, i) => ({ label, value: sums.get(label), color: `var(--series-${i + 1})`, order: i }));

  if (items.length > MAX_SLICES) {
    const sorted = [...items].sort((a, b) => b.value - a.value);
    const keep = new Set(sorted.slice(0, MAX_SLICES - 1).map((s) => s.label));
    const kept = items.filter((s) => keep.has(s.label)).map((s, i) => ({ ...s, color: `var(--series-${i + 1})` }));
    const otherValue = items.filter((s) => !keep.has(s.label)).reduce((a, s) => a + s.value, 0);
    items = [...kept, { label: "אחר", value: otherValue, color: "var(--series-other)" }];
  }
  return items
    .filter((s) => s.value > 0)
    .map((s) => ({ ...s, share: sum ? s.value / sum : 0 }));
}

function colorForHolding(h, list) {
  const k = h[state.groupBy];
  const s = list.find((x) => x.label === k);
  return s ? s.color : "var(--series-other)";
}

// ---------- Rendering ----------
function render() {
  renderTable();
  renderChart();
}

function renderTable() {
  const sum = total();
  const list = slices();
  tbody.innerHTML = "";
  for (const h of state.holdings) {
    const tr = document.createElement("tr");
    const v = valueOf(h);
    tr.innerHTML = `
      <td><span class="swatch" style="background:${colorForHolding(h, list)}"></span><span class="n"></span></td>
      <td class="t"></td>
      <td class="num">${number.format(h.quantity)}</td>
      <td class="num">${money.format(h.price)}</td>
      <td class="num">${money.format(v)}</td>
      <td class="num">${sum ? pct(v / sum) : "—"}</td>
      <td><div class="row-actions">
        <button type="button" class="icon-btn" data-edit="${h.id}">עריכה</button>
        <button type="button" class="icon-btn delete" data-del="${h.id}">מחיקה</button>
      </div></td>`;
    tr.querySelector(".n").textContent = h.name;
    tr.querySelector(".t").textContent = h.type;
    tbody.appendChild(tr);
  }
  $("#total-cell").textContent = money.format(sum);
  $("#empty-msg").hidden = state.holdings.length > 0;
  $("#holdings-table tfoot").hidden = state.holdings.length === 0;
}

tbody.addEventListener("click", (e) => {
  const edit = e.target.closest("[data-edit]");
  const del = e.target.closest("[data-del]");
  if (edit) startEdit(edit.dataset.edit);
  if (del) remove(del.dataset.del);
});

const CX = 120, CY = 120, R_OUT = 110, R_IN = 74;
const GAP = 0.012; // small gap between slices (in radians)

function arcPath(a0, a1) {
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const p = (r, a) => [CX + r * Math.sin(a), CY - r * Math.cos(a)];
  const [x0, y0] = p(R_OUT, a0), [x1, y1] = p(R_OUT, a1);
  const [x2, y2] = p(R_IN, a1), [x3, y3] = p(R_IN, a0);
  return `M${x0},${y0} A${R_OUT},${R_OUT} 0 ${large} 1 ${x1},${y1} L${x2},${y2} A${R_IN},${R_IN} 0 ${large} 0 ${x3},${y3} Z`;
}

function renderChart() {
  const list = slices();
  const sum = total();
  svg.innerHTML = "";
  $("#center-value").textContent = money.format(sum);

  if (!list.length) {
    svg.innerHTML = `<circle cx="${CX}" cy="${CY}" r="${(R_OUT + R_IN) / 2}" fill="none" stroke="var(--border)" stroke-width="${R_OUT - R_IN}"/>`;
  } else if (list.length === 1) {
    svg.innerHTML = `<circle cx="${CX}" cy="${CY}" r="${(R_OUT + R_IN) / 2}" fill="none" stroke="${list[0].color}" stroke-width="${R_OUT - R_IN}"/>`;
  } else {
    let a = 0;
    list.forEach((s, i) => {
      const span = s.share * Math.PI * 2;
      const gap = span > GAP * 3 ? GAP : 0;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", arcPath(a + gap / 2, a + span - gap / 2));
      path.setAttribute("fill", s.color);
      path.dataset.index = i;
      svg.appendChild(path);
      a += span;
    });
  }

  // Legend
  const legend = $("#legend");
  legend.innerHTML = "";
  list.forEach((s, i) => {
    const li = document.createElement("li");
    li.dataset.index = i;
    li.innerHTML = `<span class="swatch" style="background:${s.color}"></span>
      <span class="label"></span><span class="pct">${pct(s.share)}</span><span class="val">${money.format(s.value)}</span>`;
    li.querySelector(".label").textContent = s.label;
    legend.appendChild(li);
  });
  renderChart.list = list;
}

// ---------- Hover (tooltip) ----------
function highlight(i, evt) {
  const list = renderChart.list || [];
  const s = list[i];
  svg.querySelectorAll("path").forEach((p) => p.classList.toggle("active", +p.dataset.index === i));
  svg.classList.toggle("hovering", s != null && list.length > 1);
  if (!s) { tooltip.hidden = true; return; }
  tooltip.innerHTML = `<strong></strong><span>${pct(s.share)} · ${money.format(s.value)}</span>`;
  tooltip.querySelector("strong").textContent = s.label;
  tooltip.hidden = false;
  const box = svg.parentElement.getBoundingClientRect();
  if (evt) {
    tooltip.style.left = evt.clientX - box.left + "px";
    tooltip.style.top = evt.clientY - box.top + "px";
  } else {
    tooltip.style.left = box.width / 2 + "px";
    tooltip.style.top = "20px";
  }
}
function clearHighlight() { highlight(-1); }

svg.addEventListener("mousemove", (e) => {
  const p = e.target.closest("path");
  p ? highlight(+p.dataset.index, e) : clearHighlight();
});
svg.addEventListener("mouseleave", clearHighlight);
$("#legend").addEventListener("mouseover", (e) => {
  const li = e.target.closest("li");
  if (li) highlight(+li.dataset.index);
});
$("#legend").addEventListener("mouseleave", clearHighlight);

// ---------- Grouping toggle ----------
document.querySelectorAll(".toggle button").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.groupBy = btn.dataset.group;
    document.querySelectorAll(".toggle button").forEach((b) => b.setAttribute("aria-pressed", b === btn));
    render();
  });
});

// ---------- Analyst (Google Gemini) ----------
const analystForm = $("#analyst-form");
const questionEl = $("#question");
const askBtn = $("#ask-btn");
const answerEl = $("#answer");

const ANALYST_ERRORS = {
  no_api_key: "האנליסט עוד לא מחובר: צריך להוסיף מפתח API של Google Gemini לקובץ ‎.env‎ ולהפעיל מחדש את השרת.",
  bad_api_key: "מפתח ה-API לא תקין. בדוק את הקובץ ‎.env‎.",
  rate_limited: "יותר מדי בקשות כרגע. נסה שוב בעוד דקה.",
  timeout: "שירות ה-AI עמוס כרגע ולא ענה בזמן. נסה שוב בעוד כמה דקות.",
  refused: "האנליסט לא יכול לענות על השאלה הזו. נסה לנסח אותה אחרת.",
};

const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Converts basic Markdown (headings, lists, bold) to safe HTML
function renderMarkdown(md) {
  const inline = (t) => escapeHtml(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  const out = [];
  let list = null, para = [];
  const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join(" "))}</p>`); para = []; } };
  const flushList = () => { if (list) { out.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; } };

  for (const raw of md.split("\n")) {
    const line = raw.trim();
    let m;
    if (!line) { flushPara(); flushList(); }
    else if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      flushPara(); flushList();
      const tag = m[1].length <= 2 ? "h3" : "h4";
      out.push(`<${tag}>${inline(m[2])}</${tag}>`);
    }
    else if ((m = line.match(/^[-*•]\s+(.*)$/)) || (m = line.match(/^\d+[.)]\s+(.*)$/))) {
      flushPara();
      const tag = /^\d/.test(line) ? "ol" : "ul";
      if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
      list.items.push(m[1]);
    }
    else if (/^(-{3,}|\*{3,})$/.test(line)) { flushPara(); flushList(); }
    else { flushList(); para.push(line); }
  }
  flushPara(); flushList();
  return out.join("");
}

async function askAnalyst(question) {
  askBtn.disabled = true;
  answerEl.hidden = false;
  answerEl.className = "answer loading";
  answerEl.textContent = "האנליסט בוחן את התיק שלך";
  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, holdings: state.holdings }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(ANALYST_ERRORS[data.error] || "משהו השתבש בפנייה לאנליסט. נסה שוב.");
    answerEl.className = "answer";
    answerEl.innerHTML = `<div class="q">שאלת: ${escapeHtml(question || "ניתוח כללי של התיק")}</div>` + renderMarkdown(data.answer);
  } catch (err) {
    answerEl.className = "answer error";
    answerEl.textContent = err.message;
  } finally {
    askBtn.disabled = false;
  }
}

analystForm.addEventListener("submit", (e) => {
  e.preventDefault();
  if (!state.holdings.length) {
    answerEl.hidden = false;
    answerEl.className = "answer error";
    answerEl.textContent = "התיק ריק – הוסף נכסים כדי שהאנליסט יוכל לנתח אותו.";
    return;
  }
  askAnalyst(questionEl.value.trim());
});

$("#chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  questionEl.value = chip.textContent;
  analystForm.requestSubmit();
});

render();
