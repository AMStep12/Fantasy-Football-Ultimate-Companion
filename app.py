# app.py
import os
import json
import streamlit as st

from draft_assistant import get_draft_recommendations, pretty_render
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

elif src == "Pas
