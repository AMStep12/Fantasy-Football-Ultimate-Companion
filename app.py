import os
import json
import streamlit as st
from draft_assistant import get_draft_recommendations, pretty_render
from utils import parse_lines

st.set_page_config(page_title="Fantasy Sports Insights", layout="centered")
st.title("🏆 Fantasy Sports Insights — Draft Assistant (MVP)")

# Connection check (optional)
api_key_present = bool(st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
if not api_key_present:
    st.info("🔐 OpenAI key not configured yet. The UI works, but recommendations will show a setup message.")

# Sport & basic league context
col1, col2 = st.columns(2)
with col1:
    sport = st.selectbox("Sport", ["NFL", "NBA", "MLB", "NHL"], index=0)
with col2:
    scoring = st.selectbox("Scoring", ["PPR", "Half-PPR", "Standard", "Category/Points (NBA/MLB/NHL)"], index=0)

col3, col4 = st.columns(2)
with col3:
    num_teams = st.number_input("League size (# teams)", min_value=6, max_value=20, value=12, step=1)
with col4:
    pick_num = st.number_input("Your next pick number", min_value=1, max_value=400, value=24, step=1)

st.markdown("### 📋 Paste your data (one player per line)")

available_txt = st.text_area(
    "Available players (paste from your draft room):",
    placeholder="Christian McCaffrey\nJa'Marr Chase\nJustin Jefferson\n..."
)

drafted_txt = st.text_area(
    "Drafted players (optional):",
    placeholder="Josh Allen\nCeeDee Lamb\nAmon-Ra St. Brown\n..."
)

roster_txt = st.text_area(
    "Your roster so far (optional):",
    placeholder="RB: Bijan Robinson\nWR: Davante Adams\nTE: Mark Andrews\n..."
)

settings = st.text_area(
    "League settings / format (optional):",
    placeholder=f"{scoring}, {num_teams}-team, roster & scoring quirks (e.g., 1QB 2RB 3WR 1TE 1FLEX)"
)

if st.button("📊 Get Draft Recommendations"):
    avail = parse_lines(available_txt)
    drafted = parse_lines(drafted_txt)
    roster = parse_lines(roster_txt)

    if not avail:
        st.warning("Please paste at least some **Available players** (one per line).")
        st.stop()

    with st.spinner("Analyzing board, value, tiers, and positional needs…"):
        result = get_draft_recommendations(
            available=avail,
            drafted=drafted,
            my_roster=roster,
            settings=settings,
            sport=sport,
            scoring=scoring,
            num_teams=int(num_teams),
            next_pick=int(pick_num),
        )

    # If result is JSON-like, render nicely; else show raw
    try:
        data = json.loads(result)
        pretty_render(data)
    except Exception:
        st.markdown("### 🧠 AI Draft Insights")
        st.markdown(result)
