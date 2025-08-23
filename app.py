# app.py
import os
import json
import streamlit as st

from draft_assistant import get_draft_recommendations_wrapper as get_draft_recommendations, pretty_render
from rankings_loader import load_rankings, clear_rankings_cache
from utils import parse_lines, minus_drafted

# --------------------
# Page setup
# --------------------
st.set_page_config(page_title="Fantasy Sports Insights — Draft Assistant", layout="centered")
st.title("🏆 Fantasy Sports Insights — Draft Assistant (MVP)")

# Optional notice if key missing (still lets UI work)
api_key_present = bool(st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
if not api_key_present:
    st.info("🔐 OpenAI key not configured yet. You can test the UI; results will show a setup message.")

# --------------------
# Draft context
# --------------------
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

# Optional knobs that help matching/strategy
col5, col6 = st.columns(2)
with col5:
    fuzzy_thresh = st.slider("Name matching sensitivity", 80, 95, 90, help="Lower if drafted names aren't being detected; higher for stricter matching.")
with col6:
    pos_priority = st.multiselect("Position priority (optional)", ["QB","RB","WR","TE","FLEX","DST","K","C","G","F","UTIL","SP","RP","OF","D"], default=[])

# --------------------
# Rankings source
# --------------------
st.markdown("### 📊 Rankings source")
src = st.radio("Source", ["Use live defaults (CSV URL)", "Upload CSV", "Paste CSV text"], horizontal=True)

override_url = None
uploaded_csv = None
pasted_csv_text = None

if src == "Use live defaults (CSV URL)":
    configured_url = st.secrets.get("RANKINGS_URLS", {}).get(sport)
    st.caption(f"Configured live URL for **{sport}**: {configured_url or 'None set'}")
    override_url = st.text_input("Override URL (optional)", placeholder="https://docs.google.com/spreadsheets/d/.../export?format=csv&gid=...")
    if st.button("🔄 Refresh live rankings cache"):
        clear_rankings_cache()
        st.success("Cache cleared. Next load will fetch fresh CSV.")

elif src == "Upload CSV":
    uploaded_csv = st.file_uploader("Upload CSV with columns: player,pos[,team]", type=["csv"])

elif src == "Paste CSV text":
    pasted_csv_text = st.text_area("Paste CSV text", placeholder="player,pos,team\nChristian McCaffrey,RB,SF\n...")

# --------------------
# User inputs: drafted/roster/settings
# --------------------
st.markdown("### 📝 Draft context")
drafted_txt = st.text_area("Drafted players so far (one per line)", placeholder="Josh Allen\nCeeDee Lamb\nAmon-Ra St. Brown\n...")
roster_txt = st.text_area("Your roster (optional, one per line)", placeholder="RB: Bijan Robinson\nWR: Davante Adams\n...")
settings = st.text_area("League settings (optional)", placeholder=f"{scoring}, {num_teams}-team, roster & scoring quirks (e.g., 1QB 2RB 3WR 1TE 1FLEX)")

# --------------------
# Action
# --------------------
if st.button("📈 Get Best Available & Picks"):
    drafted = parse_lines(drafted_txt)
    my_roster = parse_lines(roster_txt)

    # 1) Load rankings
    try:
        rankings = load_rankings(
            sport,
            uploaded_csv=uploaded_csv,
            pasted_csv_text=pasted_csv_text,
            url_override=(override_url or None),
        )
    except Exception as e:
        st.error(f"Rankings unavailable: {e}")
        st.stop()

    if not rankings:
        st.error("No rankings available. Provide a live CSV URL, upload a CSV, or paste CSV text.")
        st.stop()

    with st.expander("⬇️ Preview loaded rankings (first 10 rows)"):
        import pandas as pd
        st.dataframe(pd.DataFrame(rankings[:10]))


    # 2) Compute available = rankings - drafted (fuzzy remove)
    available_records = minus_drafted(rankings, drafted, thresh=int(fuzzy_thresh))
    if len(available_records) == 0:
        st.warning("All players in rankings appear drafted with current matching sensitivity.")
        st.stop()

    # Keep top N remaining to keep prompt small & fast
    topN = st.slider("Players to consider (top N remaining)", 40, 150, 80)
    top_available = available_records[:topN]
    available_names = [r["player"] for r in top_available]

    with st.expander("🔍 Debug view: top remaining players"):
        st.write([f'{r["player"]} ({r["pos"]}, {r["team"]})' for r in top_available[:25]])

    # 3) Build extended settings including position preferences
    pos_hint = f" | Position priority: {', '.join(pos_priority)}" if pos_priority else ""
    full_settings = (settings or "") + pos_hint

    # 4) Ask the assistant for recommendations
    with st.spinner("Analyzing board, value, tiers, and positional needs…"):
        result = get_draft_recommendations(
            available=available_names,
            drafted=drafted,
            my_roster=my_roster,
            settings=full_settings,
            sport=sport,
            scoring=scoring,
            num_teams=int(num_teams),
            next_pick=int(next_pick),
        )

    # 5) Render
    try:
        data = json.loads(result)
        pretty_render(data)
    except Exception:
        st.markdown("### 🧠 AI Draft Insights")
        st.markdown(result)
