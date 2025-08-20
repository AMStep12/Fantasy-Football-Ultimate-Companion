#GTP logic for insights
# draft_assistant.py
import openai
import streamlit as st

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def get_draft_recommendations(draft_board, settings, sport):
    prompt = f"""
You are a fantasy {sport} draft assistant.

Based on the following draft board and league settings, recommend the best players to target next.
Use tiers, positional scarcity, value vs. reach, and highlight potential sleepers.

DRAFT BOARD:
{draft_board}

LEAGUE SETTINGS:
{settings}

Output 5 top suggestions with explanations. Use bullet points for clarity.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a smart fantasy {sport} draft strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"❌ Error: {e}"
