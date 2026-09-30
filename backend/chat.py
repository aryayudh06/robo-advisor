"""Intent routing + deterministic tool layer + Gemini explanation (with data-only fallback)."""
import json, re, uuid
from .portfolio import repo, ASSETS
from .risk import get_user_risk_profile
from .rag import kb
from .gemini import generate

WINDOW = 6  # only the last 3 turns go to the model; plan/profile travel as compact context
HISTORY: dict[str, list] = {}  # conversation_id -> [{role, content}], in-memory, capped

RULES = [
    ("PORTFOLIO_COMPARISON", r"compar|bandingkan|versus|\bvs\b"),
    ("HIGHER_RETURN_QUERY", r"(higher|highest|more|best|tinggi).{0,12}(return|yield|imbal)|return.{0,12}(higher|highest|tinggi)"),
    ("LOWER_RISK_QUERY", r"(lower|lowest|less|safer|safest|rendah).{0,12}risk|risiko.{0,12}(rendah|kecil)|\bsafer\b|lebih aman"),
    ("EFFICIENT_FRONTIER_EXPLANATION", r"frontier"),
    ("RISK_PROFILE_EXPLANATION", r"why am i|risk profile|profil risiko|kenapa saya|mengapa saya"),
    ("PORTFOLIO_EXPLANATION", r"allocation|alokasi|why this|explain (this|portfolio)|why is this"),
    ("RISK_EXPLANATION", r"risk|risiko|std|standard deviation|standar deviasi|sharpe|volatil|market fall|market drop|turun"),
    ("PRODUCT_INFORMATION", r"product|produk|\bfees?\b|biaya|fund manager"),
    ("GET_PORTFOLIOS", r"option|portfolios?|portofolio|pilihan|paket|recommend|rekomendasi|suitable"),
]
HINTS = {"RISK_PROFILE_EXPLANATION": "risk profile", "EFFICIENT_FRONTIER_EXPLANATION": "efficient frontier",
         "PRODUCT_INFORMATION": "product information", "PORTFOLIO_EXPLANATION": "diversification",
         "RISK_EXPLANATION": "standard deviation risk", "HIGHER_RETURN_QUERY": "sharpe ratio",
         "LOWER_RISK_QUERY": "standard deviation"}
QUICK = {
    "RISK_PROFILE_EXPLANATION": ["Tampilkan pilihan portofolio", "Apa risiko portofolio saya?", "Jelaskan Standar Deviasi"],
    "GET_PORTFOLIOS": ["Bandingkan portofolio saya", "Portofolio mana yang return tertingginya?", "Mana yang risikonya lebih rendah?"],
    "PORTFOLIO_EXPLANATION": ["Bandingkan portofolio saya", "Apa risiko portofolio saya?", "Apa itu diversifikasi?"],
    "PORTFOLIO_COMPARISON": ["Portofolio mana yang return tertingginya?", "Jelaskan Sharpe Ratio", "Jelaskan Efficient Frontier"],
    "HIGHER_RETURN_QUERY": ["Mana yang risikonya lebih rendah?", "Jelaskan Sharpe Ratio", "Jelaskan Efficient Frontier"],
    "LOWER_RISK_QUERY": ["Portofolio mana yang return tertingginya?", "Jelaskan Standar Deviasi", "Bandingkan portofolio saya"],
    "RISK_EXPLANATION": ["Jelaskan Sharpe Ratio", "Apa itu diversifikasi?", "Tampilkan pilihan portofolio"],
    "EFFICIENT_FRONTIER_EXPLANATION": ["Tampilkan pilihan portofolio", "Jelaskan Sharpe Ratio", "Bandingkan portofolio saya"],
}
DEFAULT_QUICK = ["Kenapa saya Moderat?", "Tampilkan pilihan portofolio", "Jelaskan Efficient Frontier"]


# --- deterministic tools (spec section 14) ---
def get_portfolio_recommendations(profile): return repo.get_by_profile(profile)
def get_portfolio(pid): return repo.get_by_id(pid)
def compare_portfolios(ids): return repo.compare(ids)
def search_knowledge_base(query): return kb.search(query)
def get_product_information(): return kb.get("product-information.md")


def detect_intent(msg):
    for intent, pat in RULES:
        if re.search(pat, msg, re.I):
            return intent
    return "PORTFOLIO_EXPLANATION" if repo.find_ids(msg) else "GENERAL_FINANCIAL_EDUCATION"


pct = lambda x: f"{x * 100:.2f}%"


def display(p):  # pre-formatted strings so the model copies instead of computing
    return {"id": p["id"], "package": p["package"], "profile": p["profile"],
            "expected_return_pct": pct(p["expected_return"]), "risk_std_dev_pct": pct(p["risk"]),
            "sharpe_ratio": f"{p['sharpe']:.2f}", "allocation_pct": {a: pct(v) for a, v in p["allocation"].items()}}


def run_tools(intent, msg, selected, profile=None, plan=None):
    prof = get_user_risk_profile(profile)
    mine = get_portfolio_recommendations(prof["profile"])
    ids = repo.find_ids(msg) or ([selected] if selected and intent == "PORTFOLIO_EXPLANATION" else [])
    ctx = {"user_risk_profile": {"profile": prof["profile"], "description": prof["description"], "horizon": prof["horizon"],
                                 "return_range_pct": [pct(x) for x in prof["return_range"]],
                                 "risk_range_pct": [pct(x) for x in prof["risk_range"]]},
           "data_is_simulated": True}
    if plan:  # compact session facts instead of long history
        ctx["user_plan"] = {k: v for k, v in plan.items() if v}
        if plan.get("needs_rm"):
            ctx["note_rm"] = "Nominal di atas Rp200 juta: sarankan menghubungi RM Bahana Signature."
    ports, comp, frontier = [], None, False
    if intent == "GET_PORTFOLIOS":
        ports = mine
    elif intent == "PORTFOLIO_EXPLANATION":
        ports = [p for p in map(get_portfolio, ids) if p]
        if not ports:
            ports, ctx["note"] = mine, "No portfolio selected; ask the user to pick one of these."
    elif intent == "PORTFOLIO_COMPARISON":
        comp = compare_portfolios(ids if len(ids) >= 2 else [p["id"] for p in mine])
        ports = comp["portfolios"]
        ctx["best"] = comp["best"]
    elif intent == "HIGHER_RETURN_QUERY":
        ports = sorted(mine, key=lambda p: -p["expected_return"])
    elif intent == "LOWER_RISK_QUERY":
        ports = sorted(mine, key=lambda p: p["risk"])
    elif intent == "RISK_EXPLANATION":
        ctx["portfolios_in_profile"] = [display(p) for p in mine]
    elif intent == "EFFICIENT_FRONTIER_EXPLANATION":
        frontier = True
    if ports:
        ctx["portfolios"] = [display(p) for p in ports]
    if intent in ("HIGHER_RETURN_QUERY", "LOWER_RISK_QUERY"):
        ctx["other_profiles"] = {pr: [display(p) for p in (repo.get_by_profile(pr)[0], repo.get_by_profile(pr)[-1])]
                                 for pr in ("Konservatif", "Moderat", "Agresif")}
    docs = search_knowledge_base(f"{msg} {HINTS.get(intent, '')}")
    ctx["knowledge"] = docs
    ctx["knowledge_note"] = "" if docs else "No relevant knowledge-base entry; say the information is unavailable if asked for facts."
    return ctx, ports, comp, docs, frontier


def fallback(intent, ctx, docs):
    """Jawaban data saja bila Gemini tidak tersedia; tidak berisi konten buatan model."""
    parts, up = [], ctx["user_risk_profile"]
    if intent == "RISK_PROFILE_EXPLANATION":
        parts.append(f"Profil risiko Anda: {up['profile']}. {up['description']} Paket pada profil ini memiliki expected return {up['return_range_pct'][0]}-{up['return_range_pct'][1]} dan risiko (std dev) {up['risk_range_pct'][0]}-{up['risk_range_pct'][1]} (data simulasi).")
    for p in ctx.get("portfolios", []):
        parts.append(f"- {p['package']} ({p['id']}): return {p['expected_return_pct']}, risiko {p['risk_std_dev_pct']}, Sharpe {p['sharpe_ratio']}")
    if "best" in ctx:
        b = ctx["best"]
        parts.append(f"Return tertinggi: {b['highest_return']}. Risiko terendah: {b['lowest_risk']}. Sharpe tertinggi: {b['highest_sharpe']}.")
    if docs and not ctx.get("portfolios"):
        parts.append(docs[0]["text"].split("\n", 1)[1].strip())
    if not parts:
        parts.append("Topik ini belum tersedia di basis pengetahuan.")
    parts.append("(Penjelasan AI sedang tidak tersedia, hanya data dari sistem yang ditampilkan.)")
    return "\n".join(parts)


async def handle_chat(message, conversation_id, selected, profile=None, plan=None):
    cid = conversation_id or uuid.uuid4().hex
    intent = detect_intent(message)
    ctx, ports, comp, docs, frontier = run_tools(intent, message, selected, profile, plan)
    hist = HISTORY.setdefault(cid, [])
    try:
        answer = await generate([{"role": h["role"], "content": h["content"][:500]} for h in hist[-WINDOW:]], message, json.dumps(ctx, ensure_ascii=False))
    except Exception:
        answer = None
    answer = answer or fallback(intent, ctx, docs)
    hist += [{"role": "user", "content": message}, {"role": "assistant", "content": answer}]
    del hist[:-WINDOW]
    while len(HISTORY) > 200:
        HISTORY.pop(next(iter(HISTORY)))
    return {"conversation_id": cid, "intent": intent, "answer": answer, "portfolio_ids": [p["id"] for p in ports],
            "portfolios": ports, "comparison": comp, "show_frontier": frontier,
            "citations": [{"title": d["title"], "source": d["source"]} for d in docs],
            "quick_replies": QUICK.get(intent, DEFAULT_QUICK)}
