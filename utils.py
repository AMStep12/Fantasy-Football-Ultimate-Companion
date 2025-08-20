#Parsing and cleaning tools
import re

def parse_lines(text: str):
    """
    Split pasted text into clean lines: one player per entry.
    Removes empties, bullets, numbering, and trims whitespace.
    """
    if not text:
        return []
    lines = re.split(r"[\r\n,;]+", text)
    cleaned = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        # Remove leading bullets or numbering like "1) " or "- "
        ln = re.sub(r"^(\d+[\).\]]\s*|-+\s*|\*\s*)", "", ln)
        # Collapse multiple spaces
        ln = re.sub(r"\s{2,}", " ", ln)
        cleaned.append(ln)
    # De-dupe preserving order
    seen, out = set(), []
    for c in cleaned:
        if c.lower() not in seen:
            out.append(c)
            seen.add(c.lower())
    return out

