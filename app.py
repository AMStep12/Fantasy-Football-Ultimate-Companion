# app.py (top of file)
import os, streamlit as st
from draft_assistant import get_draft_recommendations

st.set_page_config(page_title="Fantasy Sports Insights", layout="centered")
st.title("🏈 Fantasy Sports Insights")
st.subheader("AI Draft Assistant (Beta)")


# --- Quick OpenAI connectivity test (optional) ---
from openai import OpenAI

def _test_openai():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    CANDIDATE_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-3.5-turbo"]
    last_err = None
    for m in CANDIDATE_MODELS:
        try:
            r = client.chat.completions.create(
                model=m,
                messages=[{"role":"user","content":"Reply with: OK"}],
                temperature=0.0,
            )
            return m, r.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
    raise last_err

with st.expander("🔑 OpenAI connection test"):
    if st.button("Run test"):
        try:
            model_used, msg = _test_openai()
            st.success(f"Connected! Model: {model_used} • Response: {msg}")
            st.session_state.OPENAI_MODEL = model_used
        except Exception as e:
            st.error(f"OpenAI test failed: {e}")

api_key_present = bool(st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
if not api_key_present:
    st.info("🔐 OpenAI key not configured yet. You can still try the UI; results will show a setup message.")


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
