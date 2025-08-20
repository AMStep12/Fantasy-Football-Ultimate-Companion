# rankings_loader.py
import pandas as pd
from io import StringIO

DEFAULTS = {
    "NFL": """player,pos,team
Christian McCaffrey,RB,SF
CeeDee Lamb,WR,DAL
Tyreek Hill,WR,MIA
Bijan Robinson,RB,ATL
Justin Jefferson,WR,MIN
Ja'Marr Chase,WR,CIN
Breece Hall,RB,NYJ
Amon-Ra St. Brown,WR,DET
Travis Kelce,TE,KC
A.J. Brown,WR,PHI
""",
    "NBA": """player,pos,team
Nikola Jokic,C,DEN
Luka Doncic,G,DAL
Shai Gilgeous-Alexander,G,OKC
Giannis Antetokounmpo,F,MIL
Jayson Tatum,F,BOS
""",
    "MLB": """player,pos,team
Ronald Acuña Jr.,OF,ATL
Shohei Ohtani,UT,LAD
Mookie Betts,2B/SS,LAD
Julio Rodríguez,OF,SEA
Yordan Álvarez,OF,HOU
""",
    "NHL": """player,pos,team
Connor McDavid,C,EDM
Nathan MacKinnon,C,COL
Auston Matthews,C,TOR
Leon Draisaitl,C,EDM
Mikko Rantanen,RW,COL
""",
}

def load_rankings(sport: str, uploaded_csv=None, pasted_csv_text: str | None = None):
    """
    Returns a list of dicts in rank order: [{player,pos,team}, ...]
    Accepts:
    - uploaded_csv: file-like object
    - pasted_csv_text: string containing CSV
    Falls back to DEFAULTS for the sport.
    Required columns: player,pos  (team optional)
    """
    if uploaded_csv is not None:
        df = pd.read_csv(uploaded_csv)
    elif pasted_csv_text and "," in pasted_csv_text:
        df = pd.read_csv(StringIO(pasted_csv_text))
    else:
        df = pd.read_csv(StringIO(DEFAULTS.get(sport, DEFAULTS["NFL"])))

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    if "player" not in df.columns or "pos" not in df.columns:
        raise ValueError("Rankings CSV must include at least columns: player,pos")

    if "team" not in df.columns:
        df["team"] = ""

    # Keep only relevant cols and drop empties
    df = df[["player", "pos", "team"]].fillna("")
    df = df[df["player"].str.strip() != ""]
    return df.to_dict("records")
