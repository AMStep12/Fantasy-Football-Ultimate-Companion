import os
import json
import streamlit as st
from openai import OpenAI

def _get_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

def _pick_model():
    # Prefer a modern small model; override if you tested one in session
    if "OPENAI_MODEL" in st.session_state:
        return st.session_state.OPENAI_MODEL
    return "gpt-4o-mini"

def _json_instruction():
    return (
        "Return ONLY valid JSON with this schema:\n"
        "{\n"
        '  "top_picks": [\n'
        '    {"player":"", "pos":"", "team":"", "tier":1, "adp_estimate":null, "why":""}\n'
        "  ],\n"
        '  "sleepers": [\n'
        '    {"player":"", "pos":"", "team":"", "why":""}\n'
        "  ],\n"
        '  "avoid": [\n'
        '    {"player":"", "pos":"", "team":"", "why":""}\n'
        "  ],\n"
        '  "notes": ""\n'
        "}\n"
        "No markdown, no extra text, only JSON."
    )

def get_draft_recommendations(available, drafted, my_roster, settings, sport, scoring, num_teams, next_pick):
    api_key = _get_api_key()
    if not api_key:
        return (
            "⚠️ OpenAI API key not configured.\n\n"
            "Add it in Streamlit Cloud → **Manage app → Settings → Edit secrets**:\n"
            "```\nOPENAI_API_KEY = \"sk-...\"\n```"
        )

    client = OpenAI(api_key=api_key)
    model = _pick_model()

    prompt = f"""
You are a sharp fantasy {sport} draft strategist.
Use value-based drafting, positional scarcity, bye conflicts, and roster construction to recommend the next picks.

CONTEXT:
- Sport: {sport}
- Scoring: {scoring}
- League size: {num_teams} teams
- Upcoming pick #: {next_pick}

AVAILABLE (subset from user's draft room):
{chr(10).join(available[:150])}

DRAFTED (if provided):
{chr(10).join(drafted[:200])}

MY ROSTER SO FAR (if provided):
{chr(10).join(my_roster[:100])}

LEAGUE SETTINGS / NOTES:
{settings or "N/A"}

TASKS:
1) Choose 5 top targets for the upcoming pick. Balance positional needs and value. Include a short, actionable reason. Highlight a clear and decisive best pick and reasoning as to why. Describe why each players is great pick
for their team in a few sentences.
2) List 3 sleepers (upside plays) that may be available in the next few rounds. Give solid reasoning as to why each would be a sleeper pick in this round.
3) List up to 2 players to avoid (overvalued / injury / scheme fit).
4) Add 2–3 sentence notes: roster build advice or pivot plan if a run happens.

{_json_instruction()}
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"You are a careful, data-driven fantasy {sport} draft strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        content = resp.choices[0].message.content
        # Try to extract JSON if model adds stray text
        content = content.strip()
        if content.startswith("```"):
            # remove markdown fences if present
            content = content.strip("`")
            # after stripping, sometimes a language tag remains like json\n
            content = content.split("\n", 1)[-1] if "\n" in content else content
            content = content.strip()
        # Validate JSON minimally
        json.loads(content)
        return content
    except Exception as e:
        return f"❌ Error calling OpenAI: {e}"

def pretty_render(data: dict):
    import streamlit as st
    st.markdown("## 🧠 AI Draft Insights")

    if "top_picks" in data:
        st.markdown("### 🔝 Top Picks")
        for i, p in enumerate(data["top_picks"][:5], start=1):
            st.markdown(
                f"**{i}. {p.get('player','?')} ({p.get('pos','?')}, {p.get('team','?')})** "
                f"— Tier {p.get('tier','?')} | ADP ~ {p.get('adp_estimate','?')}  \n"
                f"{p.get('why','')}"
            )

    if "sleepers" in data and data["sleepers"]:
        st.markdown("### 🌙 Sleepers")
        for p in data["sleepers"][:5]:
            st.markdown(f"- **{p.get('player','?')} ({p.get('pos','?')}, {p.get('team','?')})** — {p.get('why','')}")

    if "avoid" in data and data["avoid"]:
        st.markdown("### 🚫 Players to Avoid")
        for p in data["avoid"][:3]:
            st.markdown(f"- **{p.get('player','?')} ({p.get('pos','?')}, {p.get('team','?')})** — {p.get('why','')}")

    if "notes" in data and data["notes"]:
        st.markdown("### 📝 Notes")
        st.markdown(data["notes"])
