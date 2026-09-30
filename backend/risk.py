"""Risk profile stub. Replace get_user_risk_profile() with your existing risk engine/questionnaire result."""
import os
from .portfolio import repo, norm_profile

# Placeholder copy: only the Moderat text/horizon comes from the spec. Replace the rest.
COPY = {"Moderat": ("Tolerates investment risk but prefers controlled volatility.", "3-5 years"),
        "Konservatif": ("Prioritises stability of capital over higher returns.", None),
        "Agresif": ("Accepts high volatility in pursuit of higher returns.", None)}


def get_user_risk_profile(profile=None):
    prof = norm_profile(profile or os.getenv("USER_RISK_PROFILE", "Moderat")) or "Moderat"
    ps = repo.get_by_profile(prof)
    desc, horizon = COPY[prof]
    return {"profile": prof, "description": desc, "horizon": horizon,
            "return_range": [min(p["expected_return"] for p in ps), max(p["expected_return"] for p in ps)],
            "risk_range": [min(p["risk"] for p in ps), max(p["risk"] for p in ps)]}
