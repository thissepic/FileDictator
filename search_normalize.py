# search_normalize.py
import re

DE_MAP = {
    "ä": ["a", "ae"],
    "ö": ["o", "oe"],
    "ü": ["u", "ue"],
    "Ä": ["A", "Ae"],
    "Ö": ["O", "Oe"],
    "Ü": ["U", "Ue"],
    "ß": ["ss"],
}
REV_MAP = {"ae": ["ä", "a"], "oe": ["ö", "o"], "ue": ["ü", "u"], "ss": ["ß", "s"]}


def de_variants(token: str) -> set[str]:
    vars = {token}
    # 1) Umlauts → {base, digraph}
    for i, ch in enumerate(token):
        if ch in DE_MAP:
            new = set()
            for v in vars:
                for rep in DE_MAP[ch]:
                    new.add(v[:i] + rep + v[i + 1 :])
            vars |= new
    # 2) Digraphs → {with umlaut, base}
    for s, reps in REV_MAP.items():
        if s in token.lower():
            new = set()
            for v in list(vars):
                idx = 0
                low = v.lower()
                while True:
                    j = low.find(s, idx)
                    if j < 0:
                        break
                    for rep in reps:
                        new.add(v[:j] + rep + v[j + len(s) :])
                    idx = j + 1
            vars |= new
    return {v for v in vars}


def expand_fts_query(q: str, for_prefix=True) -> str:
    # Liberal token split
    toks = re.findall(r"[A-Za-zÀ-ÿ0-9_+-]+", q)
    if not toks:
        return q
    parts = []
    for t in toks:
        vs = de_variants(t)
        if for_prefix and len(t) >= 4:
            vs = {v + "*" for v in vs}  # prefix search accelerated via prefix='2 3 4'
        parts.append("(" + " OR ".join(sorted(vs)) + ")")
    return " AND ".join(parts)
