# utils.py
import re
import unicodedata
from rapidfuzz import fuzz

def parse_lines(text: str):
    """Split pasted text into clean lines: one name per entry."""
    if not text:
        return []
    lines = re.split(r"[\r\n,;]+", text)
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        ln = re.sub(r"^(\d+[\).\]]\s*|-+\s*|\*\s*)", "", ln)  # remove bullets/numbers
        ln = re.sub(r"\s{2,}", " ", ln)
        out.append(ln)
    # de-dupe case-insensitively
    seen = set(); deduped=[]
    for x in out:
        k = x.lower()
        if k not in seen:
            seen.add(k); deduped.append(x)
    return deduped

def normalize_name(name: str):
    s = unicodedata.normalize('NFKD', name).encode('ascii','ignore').decode('ascii')
    s = s.lower()
    s = re.sub(r"[^a-z\s\.\-\'/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def minus_drafted(rankings: list[dict], drafted_list: list[str], thresh: int = 90):
    """
    Given rankings [{player,pos,team}, ...] and drafted names list,
    return rankings with drafted removed using fuzzy matching.
    """
    drafted_norm = [normalize_name(x) for x in drafted_list]
    available = []
    for row in rankings:
        p_norm = normalize_name(row["player"])
        taken = False
        for d in drafted_norm:
            if fuzz.ratio(p_norm, d) >= thresh:
                taken = True; break
        if not taken:
            available.append(row)
    return available
