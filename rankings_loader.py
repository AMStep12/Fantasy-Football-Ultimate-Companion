# rankings_loader.py
import os
import pandas as pd
from io import StringIO

DATA_FILES = {
    "NFL": "data/nfl_default_rankings.csv",
    "NBA": "data/nba_default_rankings.csv",
    "MLB": "data/mlb_default_rankings.csv",
    "NHL": "data/nhl_default_rankings.csv",
}

DEFAULTS = {  # keep as last-resort demo fallback
    "NFL": "player,pos,team\nChristian McCaffrey,RB,SF\nCeeDee Lamb,WR,DAL\nTyreek Hill,WR,MIA\n",
    "NBA": "player,pos,team\nNikola Jokic,C,DEN\nLuka Doncic,G,DAL\n",
    "MLB": "player,pos,team\nShohei Ohtani,UT,LAD\nMookie Betts,2B/SS,LAD\n",
    "NHL": "player,pos,team\nConnor McDavid,C,EDM\nAuston Matthews,C,TOR\n",
}

def load_rankings(sport: str, uploaded_csv=None, pasted_csv_text: str | None = None):
    # 1) user-provided sources
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
    elif pasted_csv_text and "," in pasted_csv_text:
        df = pd.read_csv(StringIO(pasted_csv_text))
    # 2) repo defaults, versioned per sport
    elif (p := DATA_FILES.get(sport)) and os.path.exists(p):
        df = pd.read_csv(p)
    # 3) tiny hardcoded fallback (demo only)
    else:
        df = pd.read_csv(StringIO(DEFAULTS.get(sport, DEFAULTS["NFL"])))

    df.columns = [c.strip().lower() for c in df.columns]
    if "player" not in df.columns or "pos" not in df.columns:
        raise ValueError("Rankings CSV must include at least columns: player,pos")
    if "team" not in df.columns:
        df["team"] = ""
    df = df[["player", "pos", "team"]].fillna("")
    df = df[df["player"].str.strip() != ""]
    return df.to_dict("records")
