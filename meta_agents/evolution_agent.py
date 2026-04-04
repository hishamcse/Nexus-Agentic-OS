"""
Nexus — Self-Evolution Engine
After an agent accumulates task history, the Evolution Engine:
  1. Critic reviews the task history and identifies weaknesses
  2. Code Generator writes an improved v2 agent
  3. Validator runs v2 through full 3-stage check
  4. Arena runs v1 vs v2 on a benchmark task
  5. If v2 wins → deploy replaces v1, lineage tracked
"""
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, GENERATED_DIR
from registry import get_agent, update_agent, register_agent
from memory_store import get_memory
from sandbox import full_validation

CRITIC_SYSTEM = """You are a code quality critic reviewing an AI agent's task history.
Analyse the task/output pairs and identify concrete weaknesses in the agent's behaviour.

Return ONLY valid JSON:
{
  "weaknesses": ["<specific weakness 1>", "<specific weakness 2>", "<specific weakness 3>"],
  "improvement_directives": ["<concrete instruction for v2>", "<instruction>"],
  "benchmark_task": "<a representative task that would reveal the improvements>",
  "critique_summary": "<2 sentences on what v1 does poorly>"
}"""

EVOLVER_SYSTEM = """You are the Code Generator inside Nexus Agent OS, writing an IMPROVED version of an existing agent.
You have the original agent.py code and a list of weaknesses to fix.

RULES:
1. Generate ONLY the Python code — no markdown, no backticks, no explanation
2. Keep the same agent_id, OLLAMA_BASE_URL, OLLAMA_MODEL setup
3. The file must work with: python agent.py --mode test  (prints TEST_OK:)
4. The file must work with: python agent.py --mode task --input "..."
5. Wrap all LLM calls in try/except
6. Improve the SYSTEM_PROMPT and logic specifically to address the weaknesses
7. Do NOT change the overall structure — improve the prompt and logic quality
Generate the COMPLETE improved file. No markdown. Start with the docstring."""


def run_evolution(agent_id: str) -> dict:
    """
    Full evolution pipeline for one agent.
    Returns a dict with evolution results.
    """
    agent = get_agent(agent_id)
    if not agent:
        return {"error": f"Agent {agent_id} not found"}

    history = get_memory(agent_id)
    if len(history) < 2:
        return {"error": "Need at least 2 task interactions to evolve. Run more tasks first."}

    code_path = Path(agent.get("code_path", ""))
    agent_py  = code_path / "agent.py"
    if not agent_py.exists():
        return {"error": "agent.py not found"}

    original_code = agent_py.read_text()
    spec = agent.get("spec", {})

    # ── Step 1: Critic ──────────────────────────────────────────────────────
    critique = _run_critic(history, spec)
    weaknesses   = critique.get("weaknesses", [])
    directives   = critique.get("improvement_directives", [])
    benchmark    = critique.get("benchmark_task", "Explain what you do.")
    summary      = critique.get("critique_summary", "")

    # ── Step 2: Generate v2 ─────────────────────────────────────────────────
    v2_code = _run_evolver(original_code, weaknesses, directives, spec)

    # ── Step 3: Write v2 to disk ────────────────────────────────────────────
    v2_id  = f"{agent_id}-v2-{uuid.uuid4().hex[:4]}"
    v2_dir = GENERATED_DIR / v2_id
    v2_dir.mkdir(exist_ok=True)

    v2_py = v2_dir / "agent.py"
    v2_py.write_text(v2_code)

    # Copy spec
    spec_src = code_path / "spec.json"
    if spec_src.exists():
        shutil.copy(spec_src, v2_dir / "spec.json")

    # ── Step 4: Validate v2 ─────────────────────────────────────────────────
    val_result = full_validation(str(v2_dir), v2_code)
    v2_valid = val_result["status"] == "pass"

    if not v2_valid:
        return {
            "agent_id":       agent_id,
            "v2_id":          v2_id,
            "critique":       critique,
            "v2_valid":       False,
            "validation_error": val_result.get("error_trace", "Unknown"),
            "deployed":       False,
            "message":        "v2 failed validation — original agent unchanged",
        }

    # ── Step 5: Arena v1 vs v2 ──────────────────────────────────────────────
    from registry import run_task_on_agent as _run_task
    # Register v2 temporarily for arena
    v2_record = {
        "agent_id":    v2_id,
        "agent_name":  f"{agent.get('agent_name','')} v2",
        "purpose":     agent.get("purpose", ""),
        "code_path":   str(v2_dir),
        "spec":        spec,
        "status":      "idle",
        "task_count":  0,
        "restart_count": 0,
    }
    register_agent(v2_id, v2_record)

    from arena import run_arena
    arena_result = run_arena(agent_id, v2_id, benchmark)
    winner_id    = arena_result.get("winner_id", "tie")

    # ── Step 6: Deploy v2 if it won ─────────────────────────────────────────
    deployed = False
    if winner_id == v2_id:
        # Replace v1 code with v2 code
        agent_py.write_text(v2_code)
        # Track lineage
        lineage = agent.get("lineage", [])
        lineage.append({
            "version":    "v2",
            "evolved_at": datetime.now(timezone.utc).isoformat(),
            "v2_id":      v2_id,
            "benchmark":  benchmark,
        })
        update_agent(agent_id, {
            "lineage":    lineage,
            "evolved_at": datetime.now(timezone.utc).isoformat(),
            "version":    len(lineage) + 1,
        })
        deployed = True

    # Deregister temp v2 agent (it's been merged or discarded)
    from registry import deregister_agent, stop_agent
    stop_agent(v2_id)
    deregister_agent(v2_id)

    return {
        "agent_id":       agent_id,
        "v2_id":          v2_id,
        "critique":       critique,
        "weaknesses":     weaknesses,
        "directives":     directives,
        "benchmark":      benchmark,
        "v2_valid":       v2_valid,
        "arena_winner":   winner_id,
        "deployed":       deployed,
        "arena_result":   arena_result,
        "message": (
            f"v2 won the arena and replaced v1 — {agent_id} is now evolved"
            if deployed else
            f"v2 did not beat v1 (winner: {winner_id}) — original unchanged"
        ),
    }


def _run_critic(history: list, spec: dict) -> dict:
    llm = ChatOpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama",
        model=OLLAMA_MODEL, temperature=0.3,
    )
    history_text = "\n\n".join(
        f"Task: {e['task'][:200]}\nOutput: {e['output'][:300]}"
        for e in history[-8:]
    )
    prompt = f"""Agent purpose: {spec.get('purpose', 'Unknown')}
Agent system prompt: {spec.get('system_prompt', '')[:300]}

TASK HISTORY (recent interactions):
{history_text}

Analyse the weaknesses. Return JSON only."""

    resp = llm.invoke([SystemMessage(content=CRITIC_SYSTEM), HumanMessage(content=prompt)])
    clean = re.sub(r"```(?:json)?|<think>.*?</think>", "", resp.content, flags=re.DOTALL).strip().strip("`")
    try:
        return json.loads(clean)
    except Exception:
        return {
            "weaknesses": ["Response quality could be improved"],
            "improvement_directives": ["Be more specific and detailed in responses"],
            "benchmark_task": "Describe what you do in detail.",
            "critique_summary": "Agent shows room for improvement.",
        }


def _run_evolver(original_code: str, weaknesses: list, directives: list, spec: dict) -> str:
    llm = ChatOpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama",
        model=OLLAMA_MODEL, temperature=0.35,
    )
    weakness_text  = "\n".join(f"- {w}" for w in weaknesses)
    directive_text = "\n".join(f"- {d}" for d in directives)

    prompt = f"""ORIGINAL AGENT CODE:
{original_code[:3000]}

IDENTIFIED WEAKNESSES:
{weakness_text}

IMPROVEMENT DIRECTIVES FOR v2:
{directive_text}

Write the COMPLETE improved agent.py. Fix the weaknesses. No markdown. Start with docstring."""

    resp = llm.invoke([SystemMessage(content=EVOLVER_SYSTEM), HumanMessage(content=prompt)])
    code = resp.content
    code = re.sub(r"<think>.*?</think>", "", code, flags=re.DOTALL).strip()
    code = re.sub(r"^```(?:python)?\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"\n?```$", "", code, flags=re.MULTILINE)
    return code.strip()


def render_evolution_result(result: dict) -> str:
    """Render evolution result as rich HTML panel."""
    import html as _html

    if result.get("error"):
        return f'<div class="nx-deploy-error">✗ Evolution failed — {_html.escape(result["error"])}</div>'

    deployed  = result.get("deployed", False)
    winner    = result.get("arena_winner", "?")
    valid     = result.get("v2_valid", False)
    weaknesses = result.get("weaknesses", [])
    directives = result.get("directives", [])
    benchmark  = result.get("benchmark", "")
    message    = result.get("message", "")
    critique   = result.get("critique", {})

    status_color  = "var(--green)" if deployed else "var(--amber)"
    status_icon   = "✓ EVOLVED" if deployed else "○ UNCHANGED"
    border_color  = "rgba(74,222,128,0.3)" if deployed else "rgba(246,173,85,0.25)"

    weaknesses_html = "".join(
        f'<div style="font-family:var(--mono);font-size:10px;color:var(--red);padding:3px 0;border-bottom:.5px solid var(--border)">⚠ {_html.escape(w)}</div>'
        for w in weaknesses
    )
    directives_html = "".join(
        f'<div style="font-family:var(--mono);font-size:10px;color:var(--cyan);padding:3px 0;border-bottom:.5px solid var(--border)">→ {_html.escape(d)}</div>'
        for d in directives
    )

    arena_html = ""
    if result.get("arena_result"):
        from arena import render_arena_result_html
        arena_html = render_arena_result_html(result["arena_result"])

    return f"""
<div class="nx-panel" style="border-color:{border_color};margin-bottom:14px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
    <div style="font-family:var(--mono);font-size:13px;font-weight:600;color:{status_color}">{status_icon}</div>
    <div style="font-family:var(--mono);font-size:10px;color:var(--muted)">{_html.escape(message)}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
    <div>
      <div class="nx-panel-label">Weaknesses identified</div>
      {weaknesses_html if weaknesses_html else '<div style="color:var(--muted);font-size:11px">None identified</div>'}
    </div>
    <div>
      <div class="nx-panel-label">Improvement directives for v2</div>
      {directives_html if directives_html else '<div style="color:var(--muted);font-size:11px">None</div>'}
    </div>
  </div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:6px">BENCHMARK TASK USED</div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--amber);margin-bottom:14px">{_html.escape(benchmark)}</div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:4px">ARENA: v1 vs v2</div>
  {arena_html}
</div>"""