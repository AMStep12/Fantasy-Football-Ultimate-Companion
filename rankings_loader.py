# rankings_loader.py
import os
from io import StringIO
import pandas as pd
import requests
import streamlit as st

# Optional local files (if you later add data/*.csv)
DATA_FILES = {
    "NFL": "data/nfl_default_rankings.csv",
    "NBA": "data/nba_default_rankings.csv",
    "MLB": "data/mlb_default_rankings.csv",
    "NHL": "data/nhl_default_rankings.csv",
}

# Tiny last-resort demo defaults (for bootstrapping only)
DEFAULTS = {
    "NFL": "player,pos,team\nChristian McCaffrey,RB,SF\nCeeDee Lamb,WR,DAL\nTyreek Hill,WR,MIA\n",
    "NBA": "player,pos,team\nNikola Jokic,C,DEN\nLuka Doncic,G,DAL\n",
    "MLB": "player,pos,team\nShohei Ohtani,UT,LAD\nMookie Betts,2B/SS,LAD\n",
    "NHL": "player,pos,team\nConnor McDavid,C,EDM\nAuston Matthews,C,TOR\n",
}

def _secrets_urls():
    try:
        return dict(st.secrets.get("RANKINGS_URLS", {}))
    except Exception:
        return {}

@st.cache_data(ttl=900, show_spinner=False)  # 15 min cache
def _fetch_csv_text(url: str) -> str:
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    return r.text

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    if "player" not in df.columns or "pos" not in df.columns:
        raise ValueError("Rankings CSV must include at least columns: player,pos")
    if "team" not in df.columns:
        df["team"] = ""
    df = df[["player", "pos", "team"]].fillna("")
    df = df[df["player"].str.strip() != ""]
    return df

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
      4) secrets: [RANKINGS_URLS][<sport>]  or env var <SPORT>_CSV_URL
      5) local data/*.csv (if present)
      6) tiny DEFAULTS
    """
    # 1) User-provided CSV file
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
        return _clean_df(df).to_dict("records")

    # 2) Pasted CSV
    if pasted_csv_text and "," in pasted_csv_text:
        df = pd.read_csv(StringIO(pasted_csv_text))
        return _clean_df(df).to_dict("records")

    # 3/4) Remote URL (override > secrets > env)
    urls = _secrets_urls()
    url = (url_override or urls.get(sport) or os.environ.get(f"{sport}_CSV_URL"))
    if url:
        text = _fetch_csv_text(url)
        df = pd.read_csv(StringIO(text))
        return _clean_df(df).to_dict("records")

    # 5) Local data file (optional)
    path = DATA_FILES.get(sport)
    if path and os.path.exists(path):
        df = pd.read_csv(path)
        return _clean_df(df).to_dict("records")

    # 6) Tiny demo fallback
    df = pd.read_csv(StringIO(DEFAULTS.get(sport, DEFAULTS["NFL"])))
    return _clean_df(df).to_dict("records")

def clear_rankings_cache():
    """Call to force-refresh remote CSVs."""
    _fetch_csv_text.clear()
