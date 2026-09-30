const $ = s => document.querySelector(s);
const PROFILE = new URLSearchParams(location.search).get("profile") || "Moderat";
const pct = x => (x * 100).toFixed(2) + "%";
const idr = n => "Rp" + Number(n).toLocaleString("id-ID");
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ASSETS = ["Pasar Uang", "Pendapatan Tetap", "Saham", "Lainnya"], ACOL = ["--a1", "--a2", "--a3", "--a4"];
const COL = { Konservatif: "#3b6ea5", Moderat: "#0e7c6b", Agresif: "#c2571a" };
const QUICK = ["Kenapa saya " + PROFILE + "?", "Tampilkan pilihan portofolio", "Kenapa alokasi ini dipakai?", "Bandingkan portofolio saya",
  "Apa risiko portofolio saya?", "Apa yang terjadi jika pasar turun?", "Jelaskan Standar Deviasi", "Jelaskan Sharpe Ratio",
  "Jelaskan Efficient Frontier", "Apa itu diversifikasi?"];
const st = { cid: null, selected: null, busy: false, last: "", cmp: [], chart: null, pts: [], qs: [], rm: null, step: 0, ans: {}, plan: null, mode: "flow", pmap: {} };

async function api(path, opts) {
  const r = await fetch("/api" + path, { headers: { "Content-Type": "application/json" }, ...opts });
  let d = null; try { d = await r.json(); } catch { }
  if (!r.ok || (d && d.error)) throw new Error((d && d.message) || "Request failed");
  return d;
}
function md(t) {
  let h = "", list = false;
  for (const l of esc(t).split("\n")) {
    const li = l.match(/^\s*[-*]\s+(.*)/);
    if (li) { if (!list) { h += "<ul>"; list = true; } h += `<li>${li[1]}</li>`; }
    else { if (list) { h += "</ul>"; list = false; } if (l.trim()) h += `<p>${l}</p>`; }
  }
  return (h + (list ? "</ul>" : "")).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}
function card(p, primary) {
  st.pmap[p.id] = p;
  const rows = ASSETS.map((a, i) => `<div class="row"><span>${a}</span><div class="bar"><i style="width:${p.allocation[a] * 100}%;background:var(${ACOL[i]})"></i></div><span>${(p.allocation[a] * 100).toFixed(0)}%</span></div>`).join("");
  return `<div class="card ${p.profile}"><h3>${esc(p.package)}</h3><small>${p.id}</small>
  <div class="kv"><span>Expected return</span><b>${pct(p.expected_return)}</b></div>
  <div class="kv"><span>Risiko / Std Dev</span><b>${pct(p.risk)}</b></div>
  <div class="kv"><span>Sharpe ratio</span><b>${p.sharpe.toFixed(2)}</b></div><div class="al">${rows}</div>
  <div class="acts"><button data-act="explain" data-id="${p.id}">Jelaskan</button><button data-act="compare" data-id="${p.id}" class="${st.cmp.includes(p.id) ? "on" : ""}">Bandingkan</button><button data-act="buy" data-id="${p.id}" class="buy">Beli</button></div></div>`;
}
function comparison(c) {
  const best = { expected_return: c.best.highest_return, risk: c.best.lowest_risk, sharpe: c.best.highest_sharpe };
  const row = (l, k, f) => `<tr><td>${l}</td>${c.portfolios.map(p => `<td class="${best[k] === p.id ? "best" : ""}">${f(p[k])}</td>`).join("")}</tr>`;
  return `<div class="cmp"><table><tr><th></th>${c.portfolios.map(p => `<th>${esc(p.package)}</th>`).join("")}</tr>
  ${row("Expected return", "expected_return", pct)}${row("Risiko / Std Dev", "risk", pct)}${row("Sharpe ratio", "sharpe", v => v.toFixed(2))}
  ${ASSETS.map(a => `<tr><td>${a}</td>${c.portfolios.map(p => `<td>${(p.allocation[a] * 100).toFixed(1)}%</td>`).join("")}</tr>`).join("")}</table></div>`;
}
function add(html, cls) {
  const m = $("#msgs"), d = document.createElement("div");
  d.className = "bubble " + cls; d.innerHTML = html; m.appendChild(d); m.scrollTop = m.scrollHeight; return d;
}
const typing = () => add('<span class="dots"><span></span><span></span><span></span></span>', "ai");
const chips = (list, attr) => `<div class="chips">${list.map(o => `<button data-${attr}="${esc(o)}">${esc(o)}</button>`).join("")}</div>`;
function setBusy(b) { st.busy = b; $("#send").disabled = b; $("#input").disabled = b; }
const fail = act => add(`Maaf, permintaan Anda tidak dapat diproses.<br><button data-act="${act}">Coba lagi</button>`, "ai err");
const rmLink = (msg) => `https://wa.me/${st.rm.wa_number}?text=${encodeURIComponent(msg)}`;

/* ---- guided flow ---- */
function ask() { const Q = st.qs[st.step]; add(`<p>${esc(Q.text)}</p>${chips(Q.options, "a")}`, "ai"); }
async function answer(text) {
  add(esc(text), "user"); document.querySelectorAll("[data-a]").forEach(b => b.disabled = true);
  st.ans[st.qs[st.step].key] = text; st.step++;
  if (st.step < st.qs.length) return ask();
  await recommend();
}
const DELTA = d => d > 0 ? `naik ${d} tingkat` : d < 0 ? `turun ${-d} tingkat` : "tetap";
const LBL = { goal: "Tujuan", horizon: "Jangka waktu", amount: "Nominal" };
async function recommend() {
  setBusy(true); const w = typing();
  try {
    const r = await api("/advice/recommend", { method: "POST", body: JSON.stringify({ profile: PROFILE, ...st.ans }) });
    w.remove(); const rec = r.recommended;
    st.plan = { ...st.ans, recommended_id: rec.id, needs_rm: r.needs_rm }; st.selected = rec.id; st.mode = "free";
    const lines = r.adjustments.map(a => `<li>${LBL[a.key]}: ${esc(a.answer || "-")} → ${a.matched ? DELTA(a.delta) : "di luar pilihan, memakai profil asli"}</li>`).join("");
    let h = `<p>Profil asli Anda <b>${esc(r.base.package)}</b>. Berdasarkan jawaban Anda, paket yang cocok adalah <b>${esc(rec.package)}</b>${r.clamped ? " (mencapai batas paket dalam profil)" : ""}.</p><ul>${lines}</ul>`;
    h += `<div class="cards">${card(rec, true)}</div>`;
    if (r.needs_rm) h += `<div class="note">Nominal di atas Rp200 juta dilayani langsung oleh RM Bahana Signature.</div><a class="wa" target="_blank" rel="noopener" href="${rmLink(`Halo RM Bahana Signature, saya tertarik ${rec.package} (${rec.id}) dengan nominal ${st.ans.amount}.`)}">Hubungi RM Bahana Signature via WhatsApp</a>`;
    if (r.alternatives.length) h += `<p class="src">Alternatif:</p>${chips(r.alternatives.map(a => `Bandingkan ${rec.id} dan ${a.id}`), "q")}`;
    h += `<p class="src">Anda bisa bertanya lebih lanjut tentang produk atau pengetahuan finansial.</p>`;
    add(h, "ai wide"); highlight([rec.id]);
    $("#quick").hidden = false; $("#input").placeholder = "Tanyakan produk atau istilah finansial…";
  } catch { w.remove(); fail("rec"); } finally { setBusy(false); }
}

/* ---- free chat ---- */
async function chat(text) {
  st.last = text; setBusy(true); add(esc(text), "user"); const w = typing();
  try {
    const r = await api("/chat", { method: "POST", body: JSON.stringify({ message: text, conversation_id: st.cid, selected_portfolio_id: st.selected, profile: PROFILE, plan: st.plan }) });
    st.cid = r.conversation_id; w.remove(); let h = md(r.answer);
    if (r.comparison) h += comparison(r.comparison); else if (r.portfolios.length) h += `<div class="cards">${r.portfolios.map(p => card(p)).join("")}</div>`;
    if (r.citations.length) h += `<div class="src">Sumber: ${r.citations.map(c => esc(c.title)).join(", ")}</div>`;
    if (r.quick_replies.length) h += chips(r.quick_replies, "q");
    add(h, "ai" + (r.portfolios.length ? " wide" : "")); if (r.portfolio_ids.length) highlight(r.portfolio_ids);
    if (r.show_frontier) openChart();
  } catch { w.remove(); fail("retry"); } finally { setBusy(false); $("#input").focus(); }
}
function send(text) {
  text = text.trim(); if (!text || st.busy) return; $("#input").value = "";
  return st.mode === "flow" ? answer(text) : chat(text);
}

/* ---- chart ---- */
function highlight(ids) {
  if (!st.chart) return;
  st.chart.data.datasets.at(-1).data = st.pts.filter(p => ids.includes(p.id)).map(p => ({ x: p.risk * 100, y: p.expected_return * 100, id: p.id }));
  st.chart.update();
}
async function openChart() {
  $("#chartSheet").hidden = false;
  if (st.chart) return;
  const fr = await api("/efficient-frontier"); st.pts = fr.points;
  const xy = p => ({ x: p.risk * 100, y: p.expected_return * 100, id: p.id }), ink = getComputedStyle(document.body).color;
  st.chart = new Chart($("#frontier"), { type: "scatter", data: { datasets: [
    { type: "line", label: "Efficient frontier", data: fr.points.map(xy), borderColor: ink + "77", borderWidth: 1.5, pointRadius: 0 },
    ...fr.profiles.map(pr => ({ label: pr, data: fr.points.filter(p => p.profile === pr).map(xy), backgroundColor: COL[pr], pointRadius: 5 })),
    { label: "Dipilih", data: [], pointRadius: 11, backgroundColor: "transparent", borderColor: ink, borderWidth: 2 }] },
    options: { maintainAspectRatio: false, scales: { x: { title: { display: true, text: "Risiko (std dev, %)" } }, y: { title: { display: true, text: "Expected return (%)" } } },
      plugins: { legend: { labels: { boxWidth: 10 } }, tooltip: { callbacks: { label: c => `${c.raw.id}: ${c.raw.y.toFixed(2)}% return, ${c.raw.x.toFixed(2)}% risiko` } } } } });
  if (st.plan) highlight([st.plan.recommended_id]);
}

/* ---- buy modal (mock) ---- */
function openBuy(id) {
  const p = st.pmap[id]; if (!p) return;
  $("#buyBody").innerHTML = `<button class="icon x" data-close>Tutup</button><h2>Beli ${esc(p.package)}</h2><small>Simulasi, tidak ada transaksi nyata</small>
  <div class="kv"><span>Expected return</span><b>${pct(p.expected_return)}</b></div><div class="kv"><span>Risiko / Std Dev</span><b>${pct(p.risk)}</b></div><div class="kv"><span>Sharpe ratio</span><b>${p.sharpe.toFixed(2)}</b></div>
  <label>Nominal pembelian<input type="text" id="buyAmt" inputmode="numeric" placeholder="Contoh: 5.000.000"></label>
  <fieldset><legend>Metode pembayaran</legend><label><input type="radio" name="pay" checked> Virtual Account</label><label><input type="radio" name="pay"> Rekening terhubung</label></fieldset>
  <label class="chk"><input type="checkbox" id="buyOk"> Saya memahami nilai investasi dapat naik dan turun, dan data ini adalah simulasi.</label>
  <div id="buyRm" hidden><div class="note">Nominal di atas Rp200 juta dilayani langsung oleh RM Bahana Signature.</div><a class="wa" target="_blank" rel="noopener" id="buyWa">Hubungi RM Bahana Signature via WhatsApp</a></div>
  <button class="primary" id="buyGo" disabled>Konfirmasi pembelian</button>`;
  $("#buySheet").hidden = false;
  const val = () => Number($("#buyAmt").value.replace(/\D/g, "") || 0);
  const upd = () => {
    const v = val(), big = v > st.rm.threshold;
    $("#buyRm").hidden = !big; $("#buyGo").hidden = big; $("#buyGo").disabled = !(v > 0 && $("#buyOk").checked);
    if (big) $("#buyWa").href = rmLink(`Halo RM Bahana Signature, saya ingin membeli ${p.package} (${p.id}) sebesar ${idr(v)}.`);
  };
  $("#buyAmt").oninput = e => { const v = val(); e.target.value = v ? v.toLocaleString("id-ID") : ""; upd(); };
  $("#buyOk").onchange = upd;
  $("#buyGo").onclick = () => {
    $("#buyBody").innerHTML = `<h2>Pesanan simulasi diterima</h2><p>${esc(p.package)} · ${idr(val())}</p><div class="note">Ref SIM-${Math.floor(100000 + Math.random() * 900000)}. Ini hanya mock: tidak ada dana yang dipindahkan.</div><button class="primary" data-close>Selesai</button>`;
  };
}

/* ---- events ---- */
document.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if ("close" in b.dataset) return b.closest(".sheet").hidden = true;
  if (b.dataset.a !== undefined) return st.busy || answer(b.dataset.a);
  if (b.dataset.q !== undefined) return st.mode === "free" && send(b.dataset.q);
  const id = b.dataset.id, act = b.dataset.act;
  if (act === "retry") return chat(st.last);
  if (act === "rec") return recommend();
  if (act === "buy") return openBuy(id);
  if (act === "explain") { st.selected = id; highlight([id]); return send(`Jelaskan ${id}`); }
  if (act === "compare") {
    st.cmp = st.cmp.includes(id) ? st.cmp.filter(x => x !== id) : [...st.cmp, id]; b.classList.toggle("on");
    $("#tray").hidden = !st.cmp.length; $("#tray").textContent = `Membandingkan ${st.cmp.join(" dan ")}. Pilih satu portofolio lagi.`;
    if (st.cmp.length === 2) { const [a, c] = st.cmp; st.cmp = []; $("#tray").hidden = true; document.querySelectorAll('[data-act="compare"].on').forEach(x => x.classList.remove("on")); send(`Bandingkan ${a} dan ${c}`); }
  }
});
$("#send").onclick = () => send($("#input").value);
$("#input").onkeydown = e => { if (e.key === "Enter") send($("#input").value); };
$("#chartBtn").onclick = openChart;

(async function init() {
  $("#quick").innerHTML = QUICK.map(q => `<button data-q="${esc(q)}">${esc(q)}</button>`).join("");
  try {
    const [rp, adv] = await Promise.all([api("/risk-profile?profile=" + encodeURIComponent(PROFILE)), api("/advice/questions")]);
    st.qs = adv.questions; st.rm = adv.rm; $("#badge").textContent = rp.profile;
    add(`<p>Halo! Profil risiko Anda <b>${esc(rp.profile)}</b>. ${esc(rp.description)}</p><p>Saya akan menanyakan 3 hal singkat untuk mencari paket yang paling sesuai. Pilih jawaban atau ketik sendiri (jawaban di luar pilihan akan memakai profil asli).</p>`, "ai");
    ask();
  } catch { $("#badge").textContent = "Offline"; add("Tidak dapat memuat data. Pastikan backend berjalan.", "ai err"); }
})();
