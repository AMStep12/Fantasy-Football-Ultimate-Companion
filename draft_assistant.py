# draft_assistant.py
import os
import streamlit as st
from openai import OpenAI

def _get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

def _pick_model():
    # Prefer the one we detected via the test button
    if "OPENAI_MODEL" in st.session_state:
        return st.session_state.OPENAI_MODEL
    # Fallback order if user didn’t run the test button
    return "gpt-4o-mini"  # adjust if needed; code will raise a clear error if not available

def get_draft_recommendations(draft_board, settings, sport):
    api_key = _get_api_key()
    if not api_key:
        return ("⚠️ OpenAI API key not configured.\n\n"
                "Add it in Streamlit Cloud under **Manage app → Settings → Edit secrets** as:\n"
                "```\nOPENAI_API_KEY = \"sk-...\"\n```")

    client = OpenAI(api_key=api_key)
    model = _pick_model()

    prompt = f"""
You are a fantasy {sport} draft assistant.

Based on the following draft board and league settings, recommend the best players to target next.
Use tiers, positional scarcity, value vs. reach, and highlight potential sleepers.

DRAFT BOARD:
{draft_board}

LEAGUE SETTINGS:
{settings}

Output 5 top suggestions with explanations. Use bullet points for clarity. The most optimal pick should be highlighted extensively based on this criteria. However, the other 4 options still shown for the optional choices. 
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"You are a smart fantasy {sport} draft strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return resp.choices[0].message.content
    except Exception as e:
        # Surface a helpful message if the model is the issue
        return (f"❌ Error calling OpenAI: {e}\n\n"
                f"Tip: Try running the 'OpenAI connection test' in the app to auto-detect a working model.")
