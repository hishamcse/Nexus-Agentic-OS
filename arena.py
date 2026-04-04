"""
Nexus — Agent Arena
Head-to-head benchmarking: run two agents on the same task simultaneously.
A Judge meta-agent scores both on accuracy, clarity, and creativity.
Results and win/loss records are persisted to memory/arena_results.json.
"""
import json
import threading
import time
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, MEMORY_DIR
from registry import run_task_on_agent, get_agent, update_agent

ARENA_FILE = MEMORY_DIR / "arena_results.json"

JUDGE_SYSTEM = """You are an impartial AI judge evaluating two agents on the same task.
Score each agent on three dimensions (0-10 each):
- accuracy:   How correct, factual, and relevant is the response?
- clarity:    How clear, well-structured, and readable is the response?
- creativity: How original, insightful, or creative is the approach?

Return ONLY valid JSON:
{
  "agent_a": {
    "accuracy": <0-10>,
    "clarity": <0-10>,
    "creativity": <0-10>,
    "total": <sum>,
    "reasoning": "<2 sentences>"
  },
  "agent_b": {
    "accuracy": <0-10>,
    "clarity": <0-10>,
    "creativity": <0-10>,
    "total": <sum>,
    "reasoning": "<2 sentences>"
  },
  "winner": "<agent_a|agent_b|tie>",
  "judge_summary": "<one decisive sentence about which agent performed better and why>"
}"""


def run_arena(agent_id_a: str, agent_id_b: str, task: str) -> dict:
    """
    Run task on both agents in parallel, then judge the results.
    Returns the full arena result dict.
    """
    results = {"a": None, "b": None}
    errors  = {"a": None, "b": None}

    def _run(agent_id: str, slot: str):
        r = run_task_on_agent(agent_id, task)
        if r.get("error"):
            errors[slot] = r["error"]
            results[slot] = ""
        else:
            results[slot] = r.get("stdout", "") or r.get("stderr", "")

    t_a = threading.Thread(target=_run, args=(agent_id_a, "a"))
    t_b = threading.Thread(target=_run, args=(agent_id_b, "b"))
    t_a.start(); t_b.start()
    t_a.join(timeout=900); t_b.join(timeout=900)

    output_a = results["a"] or f"[ERROR: {errors['a']}]"
    output_b = results["b"] or f"[ERROR: {errors['b']}]"

    # Judge
    scores = _judge(task, output_a, output_b)

    # Determine winner agent_id
    winner_slot   = scores.get("winner", "tie")
    winner_id     = agent_id_a if winner_slot == "agent_a" else (
                    agent_id_b if winner_slot == "agent_b" else "tie")

    result = {
        "arena_id":    _arena_id(),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "task":        task,
        "agent_a_id":  agent_id_a,
        "agent_b_id":  agent_id_b,
        "output_a":    output_a,
        "output_b":    output_b,
        "scores":      scores,
        "winner_id":   winner_id,
    }

    _persist(result)
    _update_win_records(agent_id_a, agent_id_b, winner_id)

    return result


def _judge(task: str, output_a: str, output_b: str) -> dict:
    llm = ChatOpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama",
        model=OLLAMA_MODEL, temperature=0.2,
    )
    prompt = f"""TASK: {task}

AGENT A OUTPUT:
{output_a[:1500]}

AGENT B OUTPUT:
{output_b[:1500]}

Score both agents and declare a winner. Return JSON only."""

    try:
        resp = llm.invoke([SystemMessage(content=JUDGE_SYSTEM), HumanMessage(content=prompt)])
        clean = re.sub(r"```(?:json)?|<think>.*?</think>", "", resp.content, flags=re.DOTALL).strip().strip("`")
        return json.loads(clean)
    except Exception as e:
        # Fallback scores
        return {
            "agent_a": {"accuracy": 5, "clarity": 5, "creativity": 5, "total": 15, "reasoning": "Judge parse error."},
            "agent_b": {"accuracy": 5, "clarity": 5, "creativity": 5, "total": 15, "reasoning": "Judge parse error."},
            "winner": "tie",
            "judge_summary": f"Judge could not parse scores: {e}",
        }


def _arena_id() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


def _persist(result: dict) -> None:
    try:
        if ARENA_FILE.exists():
            all_results = json.loads(ARENA_FILE.read_text())
        else:
            all_results = []
        all_results.append(result)
        ARENA_FILE.write_text(json.dumps(all_results[-50:], indent=2))  # keep last 50
    except Exception:
        pass


def _update_win_records(agent_id_a: str, agent_id_b: str, winner_id: str) -> None:
    """Persist win/loss/tie record onto each agent's registry entry."""
    for agent_id in [agent_id_a, agent_id_b]:
        from registry import get_agent, update_agent
        agent = get_agent(agent_id)
        if not agent:
            continue
        arena = agent.get("arena", {"wins": 0, "losses": 0, "ties": 0})
        if winner_id == "tie":
            arena["ties"] = arena.get("ties", 0) + 1
        elif winner_id == agent_id:
            arena["wins"] = arena.get("wins", 0) + 1
        else:
            arena["losses"] = arena.get("losses", 0) + 1
        update_agent(agent_id, {"arena": arena})


def list_arena_results() -> list:
    try:
        if ARENA_FILE.exists():
            return json.loads(ARENA_FILE.read_text())
        return []
    except Exception:
        return []


def render_arena_result_html(result: dict) -> str:
    """Render a single arena result as rich HTML."""
    import html as _html

    if not result:
        return ""

    scores  = result.get("scores", {})
    sa      = scores.get("agent_a", {})
    sb      = scores.get("agent_b", {})
    winner  = result.get("winner_id", "tie")
    summary = _html.escape(scores.get("judge_summary", ""))

    def _score_ring(score: float, color: str) -> str:
        pct = int((score / 10) * 100)
        return f"""<div style="text-align:center">
  <div style="font-family:var(--mono);font-size:22px;font-weight:600;color:{color}">{score:.0f}</div>
  <div style="width:100%;height:4px;background:rgba(255,255,255,0.07);border-radius:999px;overflow:hidden;margin-top:4px">
    <div style="width:{pct}%;height:100%;background:{color};border-radius:999px"></div>
  </div>
</div>"""

    def _agent_col(agent_id: str, output: str, sc: dict, slot: str) -> str:
        agent = get_agent(agent_id)
        name  = agent.get("agent_name", agent_id) if agent else agent_id
        is_winner = (winner == agent_id)
        border = "rgba(74,222,128,0.4)" if is_winner else "rgba(99,179,237,0.15)"
        winner_badge = '<span style="font-family:var(--mono);font-size:9px;background:rgba(74,222,128,0.12);border:1px solid rgba(74,222,128,0.3);color:var(--green);padding:2px 8px;border-radius:4px;margin-left:8px">WINNER</span>' if is_winner else ""
        total = sc.get("total", sc.get("accuracy",0)+sc.get("clarity",0)+sc.get("creativity",0))
        dim_color = "#4ade80" if is_winner else "#63b3ed"

        dims = f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px">
  <div><div style="font-family:var(--mono);font-size:8px;color:var(--muted);margin-bottom:3px">ACCURACY</div>{_score_ring(sc.get('accuracy',0), dim_color)}</div>
  <div><div style="font-family:var(--mono);font-size:8px;color:var(--muted);margin-bottom:3px">CLARITY</div>{_score_ring(sc.get('clarity',0), dim_color)}</div>
  <div><div style="font-family:var(--mono);font-size:8px;color:var(--muted);margin-bottom:3px">CREATIVITY</div>{_score_ring(sc.get('creativity',0), dim_color)}</div>
</div>
<div style="text-align:center;margin-bottom:10px">
  <span style="font-family:var(--mono);font-size:28px;font-weight:600;color:{dim_color}">{total}</span>
  <span style="font-family:var(--mono);font-size:10px;color:var(--muted)">/30</span>
</div>"""

        reasoning = _html.escape(sc.get("reasoning", ""))
        out_escaped = _html.escape((output or "")[:600])

        return f"""
<div style="background:var(--surface-2);border:1px solid {border};border-radius:14px;padding:16px;flex:1;min-width:0">
  <div style="font-family:var(--mono);font-size:13px;font-weight:600;color:var(--green-hi);margin-bottom:2px">{_html.escape(name)}{winner_badge}</div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:12px">{_html.escape(agent_id)}</div>
  {dims}
  <div style="font-family:var(--sans);font-size:11px;color:var(--muted);margin-bottom:8px;font-style:italic">{reasoning}</div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-bottom:4px;letter-spacing:.1em">OUTPUT</div>
  <div style="background:#050806;border-radius:8px;padding:10px;font-family:var(--mono);font-size:10px;color:#a7f3d0;line-height:1.6;max-height:180px;overflow-y:auto;white-space:pre-wrap">{out_escaped}</div>
</div>"""

    col_a = _agent_col(result["agent_a_id"], result.get("output_a",""), sa, "a")
    col_b = _agent_col(result["agent_b_id"], result.get("output_b",""), sb, "b")

    return f"""
<div class="nx-panel" style="margin-bottom:14px">
  <div class="nx-panel-label">Arena result — {_html.escape(result.get('task','')[:60])}</div>
  <div style="display:flex;gap:12px;margin-bottom:14px">{col_a}{col_b}</div>
  <div style="background:rgba(74,222,128,0.05);border:1px solid rgba(74,222,128,0.15);border-radius:10px;padding:12px;font-family:var(--sans);font-size:12px;color:var(--text);font-style:italic">
    ⚖ Judge: {summary}
  </div>
</div>"""