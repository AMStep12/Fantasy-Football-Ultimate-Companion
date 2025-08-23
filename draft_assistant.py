# draft_assistant.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
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

# ---- Value/need helpers ------------------------------------------------------

def need_weight(pos: str, state: RosterState, settings: LeagueSettings) -> float:
    """Higher weight => bigger need. Simple slope based on starters vs filled."""
    starters = settings.roster_limits.get(pos, state.starters_needed.get(pos, 0))
    have = state.roster_counts.get(pos, 0)
    gap = max(starters - have, 0)
    # small extra boost if you're thin and a run is likely before your next pick
    run_risk_boost = 0.15 if state.turns_until_next_pick >= 2 else 0.0
    base = 1.0 + 0.35 * gap + run_risk_boost
    if pos in ("RB", "WR"):
        base += 0.1  # typical league scarcity
    if pos == "QB" and settings.qb_format == "SF":
        base += 0.6
    return base

def value_over_adp(p: PlayerRow, current_pick_overall: int) -> float:
    """Positive means value vs market at this pick (fall vs ADP)."""
    if p.adp is None:
        return 0.0
    # Value = how many picks past ADP you're selecting (larger positive = better value fall)
    return float(p.adp - current_pick_overall)

def blended_score(p: PlayerRow, state: RosterState, settings: LeagueSettings) -> float:
    # Base merit mix: projections, value vs ADP, tiering
    voa = value_over_adp(p, state.pick_overall)
    proj = p.proj_pts or 0.0
    tier_adj = -0.25 * (p.tier or 5)  # lower tier number better => smaller penalty
    return 0.55 * (proj / 50.0) + 0.35 * (voa / 24.0) + 0.10 * tier_adj

def final_rank_score(p: PlayerRow, state: RosterState, settings: LeagueSettings) -> float:
    # Need multiplier applied after base merit
    return blended_score(p, state, settings) * need_weight(p.pos, state, settings)

# ---- Prompt builder ----------------------------------------------------------

SYSTEM_MSG = (
    "You are an elite fantasy football draft assistant. Be decisive, brief, and pragmatic. "
    "Assume redraft unless noted. Avoid clichés. Cite logic with data points (ADP, role, scheme, injury). "
    "Return STRICT JSON that matches the schema."
)

SCHEMA: Dict[str, Any] = {
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
    TASKS:
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
    try:
        from openai import OpenAI
    except Exception as e:
        raise ImportError(
            "OpenAI client not installed or misconfigured. "
            "Install with `pip install openai` and set OPENAI_API_KEY."
        ) from e

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"}  # ensures JSON
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Minimal salvage: strip code fences etc.
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)

# ---- Core public entry (new-style) -------------------------------------------

def get_draft_recommendations(
    candidates: List[PlayerRow],
    state: RosterState,
    settings: LeagueSettings,
    model: str = os.getenv("DRAFT_MODEL", "gpt-4o-mini"),
) -> Dict[str, Any]:
    prompt = build_prompt(candidates, state, settings)
    return call_model(prompt, model=model)

# ---- Convenience adapters (compat with older app.py calls) -------------------
# These let you call: get_draft_recommendations(available=..., next_pick=..., ...)
import pandas as _pd  # streamlit env usually has pandas

def _df_to_players(df) -> List[PlayerRow]:
    rows: List[PlayerRow] = []
    if isinstance(df, list):
        if len(df) > 0 and isinstance(df[0], str):
            # list of names
            for name in df:
                rows.append(
                    PlayerRow(
                        player=name, pos="UNK", team="UNK",
                        bye=None, ecr=None, adp=None, proj_pts=None, tier=None
                    )
                )
        elif len(df) > 0 and isinstance(df[0], dict):
            df = _pd.DataFrame(df)
        else:
            return rows

    if isinstance(df, _pd.DataFrame):
        # Expect (if present): player,pos,team,bye,ecr,adp,proj_pts,tier
        for _, r in df.iterrows():
            rows.append(
                PlayerRow(
                    player=str(r.get("player") or r.get("Player") or r.get("name") or "Unknown"),
                    pos=str(r.get("pos") or r.get("Pos") or "UNK"),
                    team=str(r.get("team") or r.get("Team") or "UNK"),
                    bye=(int(r["bye"]) if _pd.notna(r.get("bye")) else None),
                    ecr=(float(r["ecr"]) if _pd.notna(r.get("ecr")) else None),
                    adp=(float(r["adp"]) if _pd.notna(r.get("adp")) else None),
                    proj_pts=(float(r["proj_pts"]) if _pd.notna(r.get("proj_pts")) else None),
                    tier=(int(r["tier"]) if _pd.notna(r.get("tier")) else None),
                )
            )
    return rows

def _ensure_state(
    state: dict | None,
    *,
    next_pick: int | None,
    draft_round: int | None,
    turns_until_next_pick: int | None,
    roster_counts: dict | None,
    starters_needed: dict | None,
    bench_slots_left: int | None
) -> RosterState:
    return RosterState(
        picks_made=state.get("picks_made", []) if state else [],
        roster_counts=roster_counts or (state.get("roster_counts") if state else {}) or {},
        starters_needed=starters_needed or (state.get("starters_needed") if state else {}) or {},
        bench_slots_left=int(bench_slots_left if bench_slots_left is not None else (state.get("bench_slots_left", 0) if state else 0)),
        draft_round=int(draft_round if draft_round is not None else (state.get("draft_round", 1) if state else 1)),
        pick_overall=int(next_pick if next_pick is not None else (state.get("pick_overall", 1) if state else 1)),
        turns_until_next_pick=int(
            turns_until_next_pick if turns_until_next_pick is not None else (state.get("turns_until_next_pick", 2) if state else 2)
        ),
    )

def _ensure_settings(
    settings: dict | None,
    *,
    teams: int | None,
    scoring: str | None,
    qb_format: str | None,
    roster_limits: dict | None
) -> LeagueSettings:
    base = settings or {}
    return LeagueSettings(
        teams=int(teams if teams is not None else base.get("teams", 12)),
        scoring=(scoring or base.get("scoring", "PPR")),
        qb_format=(qb_format or base.get("qb_format", "1QB")),
        roster_limits=roster_limits or base.get("roster_limits", {"QB":1,"RB":2,"WR":2,"TE":1,"DST":1,"K":1}),
    )

# Private core trampoline used by both call styles
def _get_draft_recommendations_core(
    candidates: List[PlayerRow],
    state: RosterState,
    settings: LeagueSettings,
    model: str = os.getenv("DRAFT_MODEL", "gpt-4o-mini"),
) -> Dict[str, Any]:
    prompt = build_prompt(candidates, state, settings)
    return call_model(prompt, model=model)

# Wrapper that supports both signatures
def get_draft_recommendations_wrapper(*args, **kwargs) -> Dict[str, Any]:
    """
    Supports:
      1) get_draft_recommendations_wrapper(candidates, state, settings, model=...)
      2) get_draft_recommendations_wrapper(
             available=..., next_pick=..., draft_round=..., turns_until_next_pick=...,
             roster_counts=..., starters_needed=..., bench_slots_left=...,
             teams=..., scoring=..., qb_format=..., roster_limits=..., model=...
         )
    """
    # Keyword style (legacy app.py)
    if "available" in kwargs:
        available = kwargs.get("available")
        next_pick = kwargs.get("next_pick")
        draft_round = kwargs.get("draft_round")
        turns_until_next_pick = kwargs.get("turns_until_next_pick")
        roster_counts = kwargs.get("roster_counts")
        starters_needed = kwargs.get("starters_needed")
        bench_slots_left = kwargs.get("bench_slots_left")
        state_dict = kwargs.get("state", None)

        teams = kwargs.get("teams")
        scoring = kwargs.get("scoring")
        qb_format = kwargs.get("qb_format")
        roster_limits = kwargs.get("roster_limits")
        settings_dict = kwargs.get("settings", None)

        model = kwargs.get("model", os.getenv("DRAFT_MODEL", "gpt-4o-mini"))

        candidates = _df_to_players(available)
        state = _ensure_state(
            state_dict,
            next_pick=next_pick,
            draft_round=draft_round,
            turns_until_next_pick=turns_until_next_pick,
            roster_counts=roster_counts,
            starters_needed=starters_needed,
            bench_slots_left=bench_slots_left,
        )
        settings = _ensure_settings(
            settings_dict,
            teams=teams,
            scoring=scoring,
            qb_format=qb_format,
            roster_limits=roster_limits,
        )
        return _get_draft_recommendations_core(candidates, state, settings, model=model)

    # Positional style
    if len(args) >= 3 and isinstance(args[0], list):
        model = kwargs.get("model", os.getenv("DRAFT_MODEL", "gpt-4o-mini"))
        return _get_draft_recommendations_core(args[0], args[1], args[2], model=model)

    raise TypeError(
        "Unsupported arguments. "
        "Pass either (candidates, state, settings) or keywords including available= and next_pick=."
    )

# Backward compatibility: allow importing the wrapper as get_draft_recommendations if desired
# (Uncomment the next line if your app imports get_draft_recommendations with keyword style.)
# get_draft_recommendations = get_draft_recommendations_wrapper

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
