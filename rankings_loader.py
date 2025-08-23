# rankings_loader.py (flexible header mapping + live CSV support)
import os
import re
from io import StringIO
import pandas as pd
import requests
import streamlit as st

DATA_FILES = {
    "NFL": "data/nfl_default_rankings.csv",
    "NBA": "data/nba_default_rankings.csv",
    "MLB": "data/mlb_default_rankings.csv",
    "NHL": "data/nhl_default_rankings.csv",
}

DEFAULTS = {}  # disable tiny fallbacks in production

PLAYER_SYNONYMS = [
    "player", "name", "player name", "player_name", "fullname", "full name",
    "athlete", "playername"
]
POS_SYNONYMS = [
    "pos", "position", "positions", "pos.", "slot"
]
TEAM_SYNONYMS = [
    "team", "tm", "club", "franchise", "squad"
]

def _secrets_urls():
    try:
        return dict(st.secrets.get("RANKINGS_URLS", {}))
    except Exception:
        return {}

@st.cache_data(ttl=900, show_spinner=False)  # 15 minutes
def _fetch_csv_text(url: str) -> str:
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    return r.text

def _pick_col(df, synonyms):
    cols = {c.lower().strip(): c for c in df.columns}
    for syn in synonyms:
        if syn in cols:
            return cols[syn]
    # try fuzzy-ish exacts without spaces/dots
    norm = {re.sub(r"[\s\.]+", "", k): v for k, v in cols.items()}
    for syn in synonyms:
        key = re.sub(r"[\s\.]+", "", syn)
        if key in norm:
            return norm[key]
    return None

def _try_extract_team_from_player(df, player_col):
    """If team missing, try to pull uppercase abbreviations from player strings, e.g. 'Justin Jefferson (MIN)'."""
    team_guess = []
    for v in df[player_col].astype(str).fillna(""):
        m = re.search(r"\b([A-Z]{2,4})\b(?:\)|$)", v.strip())
        team_guess.append(m.group(1) if m else "")
    return team_guess

def _normalize_and_map_columns(df: pd.DataFrame) -> pd.DataFrame:
    # unify headers
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # map to canonical names
    player_src = _pick_col(df, PLAYER_SYNONYMS)
    pos_src    = _pick_col(df, POS_SYNONYMS)
    team_src   = _pick_col(df, TEAM_SYNONYMS)

    if not player_src:
        raise ValueError(
            f"Could not find a player column. Found columns: {list(df.columns)}. "
            "Expected one of: " + ", ".join(PLAYER_SYNONYMS)
        )

    out = pd.DataFrame()
    out["player"] = df[player_src].astype(str).str.strip()

    if pos_src:
        out["pos"] = df[pos_src].astype(str).str.strip()
    else:
        out["pos"] = ""  # allow missing pos (not ideal, but usable)

    if team_src:
        out["team"] = df[team_src].astype(str).str.strip()
    else:
        # attempt extraction from player cell like "Name (KC)" or "Name - KC"
        out["team"] = _try_extract_team_from_player(df, player_src)

    # basic cleanup
    out = out.fillna("")
    out = out[out["player"] != ""]
    # drop obvious extra header rows that sometimes sneak in
    mask_header = ~out["player"].str.contains(r"player|name", case=False)
    out = out[mask_header]
    return out[["player", "pos", "team"]]

def load_rankings(
    sport: str,
    uploaded_csv=None,
    pasted_csv_text: str | None = None,
    url_override: str | None = None,
):
    """
    Returns a list of dicts in rank order: [{player,pos,team}, ...].
    Priority:
      1) uploaded_csv
      2) pasted_csv_text
      3) url_override (from UI)
      4) secrets: [RANKINGS_URLS][<sport>] or env <SPORT>_CSV_URL or GLOBAL_RANKINGS_URL
      5) local data/*.csv (if present)
      6) (no tiny fallback in prod)
    """
    # 1) user upload
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
        return _normalize_and_map_columns(df).to_dict("records")

    # 2) pasted csv
    if pasted_csv_text and "," in pasted_csv_text:
        df = pd.read_csv(StringIO(pasted_csv_text))
        return _normalize_and_map_columns(df).to_dict("records")

    # 3/4) remote URL chain
    urls = _secrets_urls()
    url = (
        url_override
        or urls.get(sport)
        or os.environ.get(f"{sport}_CSV_URL")
        or st.secrets.get("GLOBAL_RANKINGS_URL")
        or os.environ.get("GLOBAL_RANKINGS_URL")
    )
    if url:
        text = _fetch_csv_text(url)
        df = pd.read_csv(StringIO(text))
        return _normalize_and_map_columns(df).to_dict("records")

    # 5) local file
    path = DATA_FILES.get(sport)
    if path and os.path.exists(path):
        df = pd.read_csv(path)
        return _normalize_and_map_columns(df).to_dict("records")

    # 6) no fallback (fail fast, clear message)
    raise ValueError(
        "No rankings source found. Provide a live CSV URL, upload a CSV, or paste CSV text. "
        "CSV must contain a player column, plus pos/team if available."
    )

def clear_rankings_cache():
    _fetch_csv_text.clear()

