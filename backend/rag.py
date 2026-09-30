"""Lightweight keyword RAG over backend/data/knowledge/*.md (no embeddings needed at this size)."""
import re
from pathlib import Path

KB_DIR = Path(__file__).parent / "data" / "knowledge"
STOP = set("the a an is are of to and or what why how do does in on for me my i am it this that with about jelaskan saya jika mana terjadi kenapa mengapa "
           "explain which has show can you your apa itu yang dan di ke dari adalah".split())


def tok(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1]


class KnowledgeBase:
    def __init__(self):
        self.docs = []
        for f in sorted(KB_DIR.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            title = text.splitlines()[0].lstrip("# ").strip()
            self.docs.append({"title": title, "source": f.name, "text": text,
                              "_t": set(tok(text)), "_h": set(tok(title))})

    def search(self, query, k=2, min_score=3):
        q = set(tok(query))
        scored = sorted(((len(q & d["_t"]) + 3 * len(q & d["_h"]), d) for d in self.docs), key=lambda x: -x[0])
        return [{x: d[x] for x in ("title", "source", "text")} for s, d in scored[:k] if s >= min_score]

    def get(self, source):
        return next(({x: d[x] for x in ("title", "source", "text")} for d in self.docs if d["source"] == source), None)


kb = KnowledgeBase()
