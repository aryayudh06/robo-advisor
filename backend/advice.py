"""Guided advice flow: answers -> step up/down inside the user's original risk profile."""
import re
from .portfolio import repo, norm_profile

BASE_INDEX = 3              # package 3 of 5 = the profile's original level
RM_THRESHOLD = 200_000_000  # above this, route to RM Bahana Signature
# delta = steps up (+) / down (-) inside the profile. PLACEHOLDER weights: validate with business/compliance.
QUESTIONS = [
    {"key": "goal", "text": "Apa tujuan investasi Anda?",
     "options": [("Dana darurat", -1), ("Pendidikan atau menikah", 0), ("Pensiun", 1), ("Pertumbuhan kekayaan", 1)]},
    {"key": "horizon", "text": "Berapa lama jangka waktu investasi Anda?",
     "options": [("< 1 tahun", -1), ("1–3 tahun", 0), ("3–5 tahun", 0), ("> 5 tahun", 1)]},
    {"key": "amount", "text": "Berapa nominal yang ingin Anda investasikan?",
     "options": [("< Rp10 juta", 0), ("Rp10–50 juta", 0), ("Rp50–200 juta", 0), ("> Rp200 juta", -1)]},
]
UNITS = {"miliar": 1e9, "milyar": 1e9, "m": 1e9, "juta": 1e6, "jt": 1e6, "ribu": 1e3, "rb": 1e3}


def parse_amount(text):
    m = re.search(r"(\d[\d.,]*)\s*(miliar|milyar|m|juta|jt|ribu|rb)?\b", str(text).lower().replace("rp", ""))
    if not m:
        return None
    raw = m.group(1)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        return float(raw.replace(",", ".")) * UNITS.get(m.group(2), 1)
    except ValueError:
        return None


def recommend(profile, answers):
    prof = norm_profile(profile) or "Moderat"
    pk = repo.get_by_profile(prof)
    adj, total = [], 0
    for q in QUESTIONS:
        a = (answers.get(q["key"]) or "").strip()
        d = dict(q["options"]).get(a)  # None = not a template answer -> original profile (delta 0)
        adj.append({"key": q["key"], "answer": a or None, "matched": d is not None, "delta": d or 0})
        total += d or 0
    idx = max(1, min(5, BASE_INDEX + total))
    amt = (answers.get("amount") or "").strip()
    needs_rm = amt == QUESTIONS[2]["options"][-1][0] or (parse_amount(amt) or 0) > RM_THRESHOLD
    return {"profile": prof, "base": pk[BASE_INDEX - 1], "recommended": pk[idx - 1],
            "alternatives": [pk[i - 1] for i in (idx - 1, idx + 1) if 1 <= i <= 5],
            "adjustments": adj, "total": total, "clamped": BASE_INDEX + total != idx, "needs_rm": needs_rm}
