# draft_assistant.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
import math
import os

# ---- Domain models -----------------------------------------------------------

@dataclass
class PlayerRow:
    player: str
    pos: str
    team: str
    bye: Optional[int]
    ecr: Optional[float]      # Expert Consensus Rank
    adp: Optional[float]      # Average Draft Position
    proj_pts: Optional[float] # Season projection
    tier: Optional[int]

@dataclass
class RosterState:
    picks_made: List[str]
    roster_counts: Dict[str, int]   # e.g. {"QB":1,"RB":2,"WR":2,"TE":0,"DST":0,"K":0}
    starters_needed: Dict[str, int] # e.g. {"QB":1,"RB":2,"WR":2,"TE":1,"FLEX":1}
    bench_slots_left: int
    draft_round: int
    pick_overall: int
    turns_until_next_pick: int      # snake awareness

@dataclass
class LeagueSettings:
    teams: int
    scoring: str       # "PPR" | "Half-PPR" | "Standard"
    qb_format: str     # "1QB" | "SF"
    roster_limits: Dict[str, int] # caps by position if any

# ---- Value/need helper -------------------------------------------------------

def need_weight(pos: str, state: RosterState, settings: LeagueSettings) -> float:
    """Higher weight => bigger need. Simple slope based on starters vs filled."""
    starters = settings.roster_limits.get(pos, state.starters_needed.get(pos, 0))
    have = state.roster_counts.get(pos, 0)
    # if FLEX, don't count; we boost WR/RB naturally via starters
    gap = max(starters - have, 0)
    # small extra boost if you're thin and a run is likely before your next pick
    run_risk_boost = 0.15 if state.turns_until_next_pick >= 2 else 0.0
    base = 1.0 + 0.35*gap + run_risk_boost
    if pos in ("RB","WR"): base += 0.1  # typical league scarcity
    if pos == "QB" and settings.qb_format == "SF": base += 0.6
    return base

def value_over_adp(p: PlayerRow, current_pick_overall: int) -> float:
    """Positive means value vs market at this pick."""
    if p.adp is None: 
        return 0.0
    # earlier pick number means earlier in draft; value if ADP < current_pick? invert carefully
    # We want 'how many picks earlier than ADP are we selecting' (negative is reach).
    # Define value = (ADP - current_pick) so larger is better (a fall).
    return float(p.adp - current_pick_overall)

def blended_score(p: PlayerRow, state: RosterState, settings: LeagueSettings) -> float:
    nw = need_weight(p.pos, state, settings)
    voa = value_over_adp(p, state.pick_overall)
    proj = p.proj_pts or 0.0
    tier_adj = -0.25 * (p.tier or 5)  # lower tier number is better; negative penalty
    # Normalize scales a bit
    return 0.55*(proj/50.0) + 0.35*(voa/24.0) + 0.10*tier_adj
    # Multiply by need after computing base merit
    # (need acts like a priority multiplier)
    # Return final:
    # NOTE: keep multiplier last so sorting stays intuitive
def final_rank_score(p: PlayerRow, state: RosterState, settings: LeagueSettings) -> float:
    return blended_score(p, state, settings) * need_weight(p.pos, state, settings)

# ---- Prompt builder ----------------------------------------------------------

SYSTEM_MSG = (
    "You are an elite fantasy football draft assistant. Be decisive, brief, and pragmatic. "
    "Assume redraft unless noted. Avoid clichés. Cite logic with data points (ADP, role, scheme, injury). "
    "Return STRICT JSON that matches the schema."
)

SCHEMA = {
  "type": "object",
  "properties": {
    "top_targets": {
      "type": "array", "minItems": 5, "maxItems": 5,
      "items": {
        "type": "object",
        "properties": {
          "player": {"type":"string"},
          "pos": {"type":"string"},
          "team": {"type":"string"},
          "best_pick": {"type":"boolean"},
          "why_best_pick": {"type":"string"},
          "why_for_team": {"type":"string"}
        },
        "required": ["player","pos","team","best_pick","why_best_pick","why_for_team"]
      }
    },
    "sleepers": {
      "type": "array", "minItems": 1, "maxItems": 3,
      "items": {
        "type": "object",
        "properties": {
          "player":{"type":"string"},
          "pos":{"type":"string"},
          "team":{"type":"string"},
          "why_sleeper":{"type":"string"}
        },
        "required":["player","pos","team","why_sleeper"]
      }
    },
    "avoids": {
      "type": "array", "minItems": 0, "maxItems": 2,
      "items": {
        "type": "object",
        "properties": {
          "player":{"type":"string"},
          "pos":{"type":"string"},
          "team":{"type":"string"},
          "reason":{"type":"string"}
        },
        "required":["player","pos","team","reason"]
      }
    },
    "notes": {"type":"string"}
  },
  "required": ["top_targets","sleepers","avoids","notes"]
}

def build_prompt(candidates: List[PlayerRow], state: RosterState,
                 settings: LeagueSettings) -> str:
    """
    TASKS (reflected verbatim):
    1) Choose 5 top targets for the upcoming pick. Balance positional needs and value. Include a short, actionable reason.
       Highlight a clear and decisive best pick and reasoning as to why. Describe why each player is a great pick
       for this team in a few sentences.
    2) List 3 sleepers (upside plays) that may be available in the next few rounds. Give solid reasoning as to why each would be a sleeper pick in this round.
    3) List up to 2 players to avoid (overvalued / injury / scheme fit).
    4) Add 2–3 sentence notes: roster build advice or pivot plan if a run happens.
    Return STRICT JSON matching the schema below.
    """
    # Sort candidates by our objective blend to encourage better choices
    ranked = sorted(candidates, key=lambda p: final_rank_score(p, state, settings), reverse=True)[:18]

    def fmt(p: PlayerRow) -> Dict[str, Any]:
        return {
            "player": p.player, "pos": p.pos, "team": p.team,
            "bye": p.bye, "ecr": p.ecr, "adp": p.adp, "proj_pts": p.proj_pts, "tier": p.tier,
            "score": round(final_rank_score(p, state, settings), 4)
        }

    context = {
        "league": settings.__dict__,
        "state": state.__dict__,
        "candidates_sorted": [fmt(p) for p in ranked],
        "schema": SCHEMA
    }

    # The model sees concise context + schema + tasks.
    return (
        "CONTEXT:\n" + json.dumps(context, ensure_ascii=False, indent=2) + "\n\n"
        "TASKS:\n"
        "1) Choose 5 top targets for the upcoming pick. Balance positional needs and value. "
        "Include a short, actionable reason. Highlight exactly ONE 'best_pick': true and include 'why_best_pick'. "
        "Describe why each player is a great pick for this team in a few sentences under 'why_for_team'.\n"
        "2) List 3 sleepers likely available in the next few rounds with 'why_sleeper'.\n"
        "3) List up to 2 avoids with 'reason'.\n"
        "4) Add 2–3 sentence 'notes' with roster build advice or pivot plan if a positional run happens.\n\n"
        "Return STRICT JSON ONLY. Do not include markdown, commentary, or extra keys.\n"
        "SCHEMA:\n" + json.dumps(SCHEMA, ensure_ascii=False)
    )

# ---- LLM call (OpenAI-style; adapt to your client) ---------------------------

def call_model(prompt: str, model: str = os.getenv("DRAFT_MODEL", "gpt-4o-mini")) -> Dict[str, Any]:
    """
    Replace this with your actual OpenAI client call. Expect a JSON string back.
    """
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system","content": SYSTEM_MSG},
            {"role":"user","content": prompt}
        ],
        temperature=0.3,
        response_format={"type":"json_object"}  # ensures JSON
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Minimal salvage: strip code fences etc.
        content = content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(content)

# ---- Public entry point ------------------------------------------------------

def get_draft_recommendations(
    candidates: List[PlayerRow],
    state: RosterState,
    settings: LeagueSettings,
    model: str = os.getenv("DRAFT_MODEL", "gpt-4o-mini"),
) -> Dict[str, Any]:
    prompt = build_prompt(candidates, state, settings)
    return call_model(prompt, model=model)


# ---- Streamlit renderer (optional helper) ------------------------------------
def pretty_render(st, recs: dict):
    """
    Render the JSON from get_draft_recommendations in a clear Streamlit layout.
    Usage:
        recs = get_draft_recommendations(...)
        pretty_render(st, recs)
    """
    if not recs:
        st.warning("No recommendations returned.")
        return

    top = recs.get("top_targets", [])
    sleepers = recs.get("sleepers", [])
    avoids = recs.get("avoids", [])
    notes = recs.get("notes", "")

    st.subheader("Top Targets (5)")
    for i, t in enumerate(top, 1):
        best = " ✅ BEST PICK" if t.get("best_pick") else ""
        st.markdown(
            f"**{i}. {t['player']} ({t['pos']} – {t['team']}){best}**  \n"
            f"- *Why best pick:* {t.get('why_best_pick','—') if t.get('best_pick') else '—'}  \n"
            f"- *Why for team:* {t.get('why_for_team','')}"
        )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Sleepers (3)")
        if not sleepers:
            st.write("—")
        for s in sleepers:
            st.markdown(
                f"**{s['player']} ({s['pos']} – {s['team']})**  \n"
                f"- {s.get('why_sleeper','')}"
            )
    with c2:
        st.subheader("Avoids (up to 2)")
        if not avoids:
            st.write("—")
        for a in avoids:
            st.markdown(
                f"**{a['player']} ({a['pos']} – {a['team']})**  \n"
                f"- {a.get('reason','')}"
            )

    if notes:
        st.markdown("---")
        st.subheader("Roster Notes / Pivot Plan")
        st.write(notes)
