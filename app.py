#streamlit frontend
# app.py
import streamlit as st
from draft_assistant import get_draft_recommendations

st.set_page_config(page_title="Fantasy Sports Insights", layout="centered")

st.title("🏈 Fantasy Sports Insights")
st.subheader("AI Draft Assistant (Beta)")

# Sport selection (default NFL)
sport = st.selectbox("Select Sport", ["NFL", "NBA", "MLB", "NHL"])

# Draft board input
draft_board = st.text_area("Paste your league's draft board or remaining players list here")

# League format/settings
league_settings = st.text_area("Paste league format/settings (e.g. PPR, roster size, scoring rules)")

# Run analysis
if st.button("📊 Get Draft Recommendations"):
    if draft_board:
        with st.spinner("Analyzing players and generating insights..."):
            insights = get_draft_recommendations(draft_board, league_settings, sport)
            st.markdown("### 🧠 AI Draft Insights")
            st.markdown(insights)
    else:
        st.warning("Please paste your draft board first.")
