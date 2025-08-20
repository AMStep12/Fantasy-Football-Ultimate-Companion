import os
import json
import streamlit as st
from draft_assistant import get_draft_recommendations, pretty_render
from rankings_loader import load_rankings
from utils import parse_lines, minus_drafted

st.set_page_config(page_title="Fantasy Sports Insights", layout="centered")
st.title("🏆 Fantasy Sports Insights — Draft Assistant (MVP)")

# Optional notice if key missing
api_key_present = bool(st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
if not api_key_present:
    st.info("🔐 OpenAI key not configured yet. The UI works, but results will show a setup message.")

# Sport & context
col1, col2 = st.columns(2)
with col1:
    sport = st.selectbox("Sport", ["NFL", "NBA", "MLB", "NHL"], index=0)
with col2:
    scoring = st.selectbox("Scoring", ["PPR", "Half-PPR", "Standard", "Cat/Points"], index=0)

col3, col4 = st.columns(2)
with col3:
    num_teams = st.number_input("League size (# teams)", min_value=6, max_value=20, value=12, step=1)
with col4:
    next_pick = st.number_input("Your next pick #", min_value=1, max_value=400, value=24, step=1)

st.markdown("### 📊 Rankings source (choose one)")
src = st.radio("Source", ["Use default rankings", "Upload CSV", "Paste CSV text"], horizontal=True)

uploaded_csv = None
pasted_csv_text = None

if src == "Upload CSV":
    uploaded_csv = st.file_uploader("Upload CSV with columns: player,pos[,team]", type=["csv"])
elif src == "Paste CSV text":
    pasted_csv_text = st.text_area("Paste CSV text", placeholder="player,pos,team\nChristian McCaffrey,RB,SF\n...")

st.markdown("### 📝 Draft context")
drafted_txt = st.text_area("Drafted players so far (one per line)", placeholder="Josh Allen\nCeeDee Lamb\n...")
roster_txt = st.text_area("Your roster (optional, one per line)", placeholder="RB: Bijan Robinson\nWR: Davante Adams\n...")
settings = st.text_area("League settings (optional)", placeholder=f"{scoring}, {num_teams}-team, roster & scoring quirks")

if st.button("📈 Get Best Available & Picks"):
    drafted = parse_lines(drafted_txt)
    my_roster = parse_lines(roster_txt)

    # 1) Load rankings (records list in rank order)
    try:
        rankings = load_rankings(sport, uploaded_csv=uploaded_csv, pasted_csv_text=pasted_csv_text)
    except Exception as e:
        st.error(f"Problem loading rankings: {e}")
        st.stop()

    if not rankings:
        st.error("No rankings available. Provide a CSV or use defaults.")
        st.stop()

    # 2) Compute available = rankings - drafted (fuzzy)
    available_records = minus_drafted(rankings, drafted, thresh=90)  # returns list of dicts
    # Keep only top N remaining to keep prompt small
    top_available = available_records[:80]
    available_names = [r['player'] for r in top_available]

    if len(available_names) == 0:
        st.warning("All players in your rankings appear drafted. Try lowering the fuzzy threshold or check names.")
        st.stop()

    with st.spinner("Analyzing board, value, tiers, and positional needs…"):
        result = get_draft_recommendations(
            available=available_names,
            drafted=drafted,
            my_roster=my_roster,
            settings=settings,
            sport=sport,
            scoring=scoring,
            num_teams=int(num_teams),
            next_pick=int(next_pick),
        )

    # Render JSON nicely if possible
    try:
        data = json.loads(result)
        pretty_render(data)
    except Exception:
        st.markdown("### 🧠 AI Draft Insights")
        st.markdown(result)
