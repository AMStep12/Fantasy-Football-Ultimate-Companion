# draft_assistant.py
import os
import streamlit as st
from openai import OpenAI

def _get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

def get_draft_recommendations(draft_board, settings, sport):
    api_key = _get_api_key()
    if not api_key:
        # Graceful message when not configured yet
        return (
            "⚠️ OpenAI API key not configured.\n\n"
            "Add it in Streamlit Cloud under **Manage app → Settings → Edit secrets** as:\n\n"
            "```\nOPENAI_API_KEY = \"sk-...\"\n```\n"
        )

    client = OpenAI(api_key=api_key)

    prompt = f"""
You are a fantasy {sport} draft assistant.

Based on the following draft board and league settings, recommend the best players to target next.
Use tiers, positional scarcity, value vs. reach, and highlight potential sleepers.

DRAFT BOARD:
{draft_board}

LEAGUE SETTINGS:
{settings}

Output 5 top suggestions with explanations. Use bullet points for clarity.Highlight the absolute best pick,but include the other 4 for options.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a smart fantasy {sport} draft strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"❌ Error calling OpenAI: {e}"
