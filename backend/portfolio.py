"""PortfolioRepository: the CSV is the single source of truth for packages."""
import re
from pathlib import Path
import pandas as pd

CSV_PATH = Path(__file__).parent / "data" / "mapping_paket_reksadana_efficient_frontier.csv"
PREFIX = {"Konservatif": "KON", "Moderat": "MOD", "Agresif": "AGR"}
ALIASES = {"konservatif": "Konservatif", "conservative": "Konservatif", "moderat": "Moderat",
           "moderate": "Moderat", "agresif": "Agresif", "aggressive": "Agresif"}
ASSETS = ["Pasar Uang", "Pendapatan Tetap", "Saham", "Lainnya"]


def norm_profile(name):
    return ALIASES.get(str(name).strip().lower())


def _clean(x):  # drop float noise such as 4.7e-17; values stay fractions (0.09 = 9%)
    x = float(x)
    return 0.0 if abs(x) < 1e-9 else round(x, 6)


class PortfolioRepository:
    def __init__(self, path=CSV_PATH):
        df = pd.read_csv(path)
        self._items = []
        for _, r in df.iterrows():
            n = int(str(r["Package"]).split()[-1])
            self._items.append({
                "id": f"{PREFIX[r['Profile']]}-{n:02d}", "package": r["Package"], "profile": r["Profile"],
                "expected_return": _clean(r["Expected Return"]), "risk": _clean(r["Risk / Std Dev"]),
                "sharpe": round(float(r["Sharpe Ratio"]), 4),
                "allocation": {a: _clean(r[a]) for a in ASSETS},
            })
        self._by_id = {p["id"]: p for p in self._items}

    @staticmethod
    def find_ids(text):
        """Find ids in free text: 'MOD-03', 'mod3', 'Moderat 3', 'Moderate 3'."""
        ids = []
        for m in re.finditer(r"\b(kon|mod|agr)[a-z]*[\s-]*0?([1-9])\b", str(text).lower()):
            i = f"{m.group(1).upper()}-{int(m.group(2)):02d}"
            if i not in ids:
                ids.append(i)
        return ids

    def get_all(self):
        return list(self._items)

    def get_by_profile(self, profile):
        prof = norm_profile(profile)
        return [p for p in self._items if p["profile"] == prof]

    def get_by_id(self, pid):
        ids = self.find_ids(pid)
        return self._by_id.get(ids[0] if ids else str(pid).upper())

    def compare(self, ids):
        ps = [p for p in (self.get_by_id(i) for i in ids) if p]
        if len(ps) < 2:
            raise ValueError("At least two valid portfolio ids are required")
        return {"portfolios": ps, "best": {
            "highest_return": max(ps, key=lambda p: p["expected_return"])["id"],
            "lowest_risk": min(ps, key=lambda p: p["risk"])["id"],
            "highest_sharpe": max(ps, key=lambda p: p["sharpe"])["id"]}}

    def frontier(self):
        pts = sorted(({"id": p["id"], "profile": p["profile"], "risk": p["risk"],
                       "expected_return": p["expected_return"]} for p in self._items), key=lambda p: p["risk"])
        return {"points": pts, "profiles": list(PREFIX),
                "note": "Points are the packages in the CSV, ordered by risk; no covariance data is available to recompute the frontier."}


repo = PortfolioRepository()
