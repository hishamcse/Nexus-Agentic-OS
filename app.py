"""
Nexus Agent OS — Gradio UI  v2
Terminal aesthetic: dark green-on-black OS dashboard.

Tabs:
  🏗  Forge           — build agents with live graph node visualiser
  📡  Mission Control — live registry dashboard
  🔬  Inspector       — run tasks, view memory, evolve agents
  ⚔️  Arena           — head-to-head agent benchmarking
  🔗  Pipelines       — chain agents into workflows
  📊  Lifecycle       — full event timeline
  🛰  Analytics       — cross-system telemetry and rankings
  🧬  Source Code     — generated code viewer
"""
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gradio as gr

from graph import NexusEngine
from registry import (
    list_agents, get_agent, ping_agent, stop_agent,
    restart_agent, run_task_on_agent, deregister_agent,
)
from memory_store import (
    get_memory, clear_memory, render_memory_html, render_memory_search_html,
    render_memory_insights_html,
)
from arena import run_arena, render_arena_result_html, list_arena_results
from pipeline import (
    run_pipeline, save_pipeline, list_pipelines, delete_pipeline,
    pipeline_choices, render_pipeline_stage, render_saved_pipelines,
    list_pipeline_runs, render_pipeline_runs,
)
from analytics import render_analytics_html
from meta_agents.monitor_agent import start_monitor_daemon, get_daemon_status
from ui.css      import APP_CSS
from ui.html     import (
    HERO_HTML, EMPTY_MISSION_HTML, EMPTY_INSPECTOR_HTML,
    EMPTY_LOG_HTML, EMPTY_CODE_HTML,
)
from ui.graph_viz import render_graph_svg

engine = NexusEngine()
start_monitor_daemon()

SAMPLE_REQUESTS = {
    "CSV Summariser":    "Build me an agent that reads a CSV dataset description and produces a plain-English statistical summary with key insights.",
    "Code Explainer":    "Create an agent that takes any Python function and explains what it does in plain English, step by step.",
    "Idea Brainstormer": "Build an agent that takes a product concept and generates 10 creative marketing angle ideas, each with a one-sentence pitch.",
    "Text Classifier":   "Make an agent that classifies a piece of text into one of these categories: News, Opinion, Tutorial, Question, or Other.",
    "SQL Generator":     "Build an agent that takes a natural language query like 'show me all orders from last month' and writes the SQL for it.",
}



def _esc(v: Any) -> str:
    return html.escape(str(v or ""))

def _status_dot(status: str) -> str:
    cls = {"running": "dot-running", "idle": "dot-idle",
           "crashed": "dot-crashed"}.get(status.lower(), "dot-stopped")
    return f'<div class="nx-status-dot {cls}"></div>'

def _status_tag(status: str) -> str:
    cls = {"running": "tag-running", "idle": "tag-idle",
           "crashed": "tag-crashed"}.get(status.lower(), "tag-stopped")
    return f'<div class="nx-agent-status-tag {cls}">{_esc(status.upper())}</div>'

def _agent_choices() -> list[str]:
    return [f"{a['agent_id']} — {a.get('agent_name','?')}" for a in list_agents()]

def _topology_choices() -> list[str]:
    topologies = sorted({
        (agent.get("spec", {}) or {}).get("graph_topology", "unknown")
        for agent in list_agents()
    })
    return ["all", *topologies] if topologies else ["all"]

def _refresh_dropdown():
    return gr.update(choices=_agent_choices(), value=None)

def _refresh_all_selectors():
    """Returns gr.update for every agent dropdown in the UI (5 total)."""
    upd = gr.update(choices=_agent_choices(), value=None)
    return upd, upd, upd, upd, upd

def _refresh_topology_dropdown():
    return gr.update(choices=_topology_choices(), value="all")

def _parse_choice(choice) -> str:
    if choice is None: return ""
    if isinstance(choice, list): choice = choice[0] if choice else ""
    return str(choice).strip()

def _extract_agent_id(choice) -> str:
    raw = _parse_choice(choice)
    if not raw or "No agents" in raw: return ""
    return raw.split("—")[0].strip()


def _filter_agents(agents: list[dict], query: str = "", status: str = "all", topology: str = "all") -> list[dict]:
    query = (query or "").strip().lower()
    status = (status or "all").strip().lower()
    topology = (topology or "all").strip().lower()

    filtered = []
    for agent in agents:
        haystack = " ".join([
            agent.get("agent_id", ""),
            agent.get("agent_name", ""),
            agent.get("purpose", ""),
            (agent.get("spec", {}) or {}).get("graph_topology", ""),
        ]).lower()
        agent_status = agent.get("status", "").lower()
        agent_topology = ((agent.get("spec", {}) or {}).get("graph_topology", "unknown")).lower()

        if query and query not in haystack:
            continue
        if status != "all" and agent_status != status:
            continue
        if topology != "all" and agent_topology != topology:
            continue
        filtered.append(agent)
    return filtered



def _render_build_log(build_log: list) -> str:
    if not build_log:
        return EMPTY_LOG_HTML
    lines = []
    for entry in build_log:
        cls = "log-default"
        if "[ARCHITECT]"  in entry: cls = "log-architect"
        elif "[SPEC"      in entry: cls = "log-spec"
        elif "[CODE GEN]" in entry: cls = "log-codegen"
        elif "[VALIDATOR]"in entry: cls = "log-validator"
        elif "[DEPLOYER]" in entry: cls = "log-deployer"
        elif "[MONITOR]"  in entry: cls = "log-monitor"
        elif "[NEXUS]"    in entry: cls = "log-nexus"
        lines.append(f'<p class="nx-log-line {cls}">{_esc(entry)}</p>')
    return f'<div class="nx-terminal">{"".join(lines)}</div>'


def _render_deploy_result(state: dict) -> str:
    if state.get("error") or state.get("escalated"):
        return f'<div class="nx-deploy-error">✗ Forge failed — {_esc(state.get("error","Unknown"))}</div>'
    deployed = state.get("deployed_agent")
    if not deployed: return ""
    agent_id   = deployed.get("agent_id","?")
    agent_name = deployed.get("agent_name","?")
    purpose    = deployed.get("purpose","")
    pid        = deployed.get("pid","N/A")
    topology   = state.get("agent_spec",{}).get("graph_topology","?") if state.get("agent_spec") else "?"
    attempts   = state.get("generation_attempt",1)
    val        = state.get("validation_result",{})
    import_ms  = val.get("import_time_ms",0) if val else 0
    return f"""
<div class="nx-deploy-success">
  ✓ Agent deployed successfully
  <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:11px">
    <div><span style="color:var(--muted)">ID</span><br>{_esc(agent_id)}</div>
    <div><span style="color:var(--muted)">Name</span><br>{_esc(agent_name)}</div>
    <div><span style="color:var(--muted)">Topology</span><br>{_esc(topology)}</div>
    <div><span style="color:var(--muted)">PID</span><br>{_esc(str(pid))}</div>
    <div style="grid-column:span 2"><span style="color:var(--muted)">Purpose</span><br>{_esc(purpose)}</div>
    <div><span style="color:var(--muted)">Validation</span><br>{attempts} attempt(s) · {import_ms:.0f}ms</div>
  </div>
</div>"""


def _render_mission_control(query: str = "", status: str = "all", topology: str = "all") -> str:
    agents = list_agents()
    if not agents: return EMPTY_MISSION_HTML
    visible_agents = _filter_agents(agents, query, status, topology)
    total    = len(agents)
    visible  = len(visible_agents)
    running  = sum(1 for a in visible_agents if a.get("status")=="running")
    tasks    = sum(a.get("task_count",0) for a in visible_agents)
    restarts = sum(a.get("restart_count",0) for a in visible_agents)
    metrics = f"""
<div class="nx-metric-grid">
  <div class="nx-metric"><div class="nx-metric-val">{visible}</div><div class="nx-metric-lbl">Visible / {total}</div></div>
  <div class="nx-metric"><div class="nx-metric-val" style="color:var(--cyan)">{running}</div><div class="nx-metric-lbl">Running</div></div>
  <div class="nx-metric"><div class="nx-metric-val" style="color:var(--amber)">{tasks}</div><div class="nx-metric-lbl">Tasks Run</div></div>
  <div class="nx-metric"><div class="nx-metric-val" style="color:var(--red)">{restarts}</div><div class="nx-metric-lbl">Restarts</div></div>
</div>"""
    if not visible_agents:
        return metrics + """<div class="nx-empty" style="margin-top:12px">
  <div class="nx-empty-icon">⌕</div>
  <div>No agents match the current filters.</div>
  <div style="margin-top:5px;opacity:0.6">Try a broader search or reset the status/topology filters.</div>
</div>"""
    cards = []
    for a in sorted(visible_agents, key=lambda x: x.get("deploy_timestamp",""), reverse=True):
        status   = a.get("status","idle")
        dot      = _status_dot(status)
        tag      = _status_tag(status)
        tc       = a.get("task_count",0)
        restart  = a.get("restart_count",0)
        pid_str  = f"PID {a.get('pid')}" if a.get("pid") else "task-mode"
        topology = a.get("spec",{}).get("graph_topology","?") if a.get("spec") else "?"
        arena    = a.get("arena", {})
        wins     = arena.get("wins",0); losses = arena.get("losses",0)
        mem_cnt  = len(get_memory(a["agent_id"]))
        version  = a.get("version", 1)
        ver_badge = f'<span style="font-family:var(--mono);font-size:9px;color:var(--blue);background:rgba(55,138,221,0.08);border:.5px solid rgba(55,138,221,0.2);padding:1px 6px;border-radius:3px">v{version}</span>' if version > 1 else ""
        cards.append(f"""
<div class="nx-agent-card">
  {dot}
  <div>
    <div class="nx-agent-name">{_esc(a.get('agent_name','?'))} {ver_badge}</div>
    <div class="nx-agent-purpose">{_esc(a.get('purpose','')[:80])}</div>
    <div style="margin-top:5px;font-family:var(--mono);font-size:9px;color:var(--dim)">
      {_esc(a.get('agent_id',''))} · {_esc(topology)} · {pid_str} · {mem_cnt}mem · {wins}W/{losses}L · {a.get('last_task_duration_ms', 0):.0f}ms
    </div>
  </div>
  <div class="nx-agent-meta">
    <div class="nx-task-count">{tc}</div>
    <div style="font-family:var(--mono);font-size:8px;color:var(--muted);margin-bottom:5px">tasks</div>
    {tag}
  </div>
</div>""")
    return metrics + f'<div class="nx-agent-grid">{"".join(cards)}</div>'


def _render_inspector_detail(agent_id: str) -> str:
    agent = get_agent(agent_id)
    if not agent: return EMPTY_INSPECTOR_HTML
    status   = agent.get("status","idle")
    purpose  = agent.get("purpose","")
    topology = agent.get("spec",{}).get("graph_topology","?") if agent.get("spec") else "?"
    tools    = agent.get("spec",{}).get("tools",[]) if agent.get("spec") else []
    tool_str = ", ".join(t.get("name","?") for t in tools) or "none"
    tc       = agent.get("task_count",0)
    mem_cnt  = len(get_memory(agent_id))
    version  = agent.get("version",1)
    lineage  = agent.get("lineage",[])
    arena    = agent.get("arena",{})
    tag  = _status_tag(status)
    dot  = _status_dot(status)
    lineage_html = ""
    if lineage:
        lineage_html = f"""<div style="grid-column:span 2">
          <span style="color:var(--muted)">Lineage</span><br>
          {"".join(f'<span style="color:var(--blue);font-family:var(--mono);font-size:9px">v{i+2} evolved {l.get("evolved_at","")[:10]} → </span>' for i,l in enumerate(lineage))}
        </div>"""
    return f"""
<div class="nx-panel">
  <div class="nx-panel-label">Selected agent</div>
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
    {dot}
    <div>
      <div style="font-family:var(--mono);font-size:14px;font-weight:600;color:var(--green-hi)">{_esc(agent.get('agent_name','?'))}</div>
      <div style="font-family:var(--mono);font-size:10px;color:var(--muted)">{_esc(agent_id)}</div>
    </div>
    <div style="margin-left:auto">{tag}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-family:var(--mono);font-size:11px;margin-bottom:12px">
    <div><span style="color:var(--muted)">Topology</span><br>{_esc(topology)}</div>
    <div><span style="color:var(--muted)">Tasks / Memory</span><br>{tc} tasks · {mem_cnt} memories</div>
    <div><span style="color:var(--muted)">Arena record</span><br>{arena.get("wins",0)}W / {arena.get("losses",0)}L / {arena.get("ties",0)}T</div>
    <div><span style="color:var(--muted)">Version</span><br>v{version}</div>
    <div style="grid-column:span 2"><span style="color:var(--muted)">Tools</span><br>{_esc(tool_str)}</div>
    <div style="grid-column:span 2"><span style="color:var(--muted)">Purpose</span><br>{_esc(purpose)}</div>
    {lineage_html}
  </div>
</div>"""


def _render_lifecycle() -> str:
    agents = list_agents()
    if not agents: return EMPTY_INSPECTOR_HTML
    rows = []
    for a in sorted(agents, key=lambda x: x.get("deploy_timestamp",""), reverse=True):
        ts_raw  = a.get("deploy_timestamp","")
        ts      = ts_raw[11:19] if len(ts_raw)>19 else ts_raw
        agent_id= a.get("agent_id","?")
        name    = a.get("agent_name","?")
        tc      = a.get("task_count",0)
        rc      = a.get("restart_count",0)
        req     = a.get("user_request","")[:60]
        events  = [
            ("designed",  f"Architect + Spec Writer designed {_esc(name)}"),
            ("generated", f"Code Generator wrote agent.py ({_esc(a.get('spec',{}).get('graph_topology','?') if a.get('spec') else '?')} topology)"),
            ("validated", "Validator passed all 3 stages"),
            ("deployed",  f"Deployer registered {_esc(agent_id)}"),
        ]
        if rc > 0: events.append(("restarted", f"Monitor restarted {rc} time(s)"))
        if tc > 0: events.append(("tasks",     f"{tc} task(s) completed"))
        if a.get("lineage"): events.append(("evolved", f"Self-evolved {len(a['lineage'])} time(s)"))
        tl_rows = []
        for j,(label,desc) in enumerate(events):
            is_last = j==len(events)-1
            dc = {"designed":"var(--blue)","generated":"var(--amber)","validated":"var(--cyan)",
                  "deployed":"var(--green)","restarted":"var(--red)","tasks":"var(--purple)",
                  "evolved":"var(--blue)"}.get(label,"var(--muted)")
            line = "" if is_last else '<div class="nx-tl-line"></div>'
            tl_rows.append(f"""
<div class="nx-tl-row">
  <div class="nx-tl-time">{ts if j==0 else ""}</div>
  <div class="nx-tl-dot-col"><div class="nx-tl-dot" style="border-color:{dc};background:var(--surface)"></div>{line}</div>
  <div class="nx-tl-content"><span style="color:{dc};font-weight:600">{label.upper()}</span><div class="nx-tl-meta">{desc}</div></div>
</div>""")
        rows.append(f'<div class="nx-panel" style="margin-bottom:12px"><div class="nx-panel-label">{_esc(agent_id)} · {_esc(req)}</div><div class="nx-timeline">{"".join(tl_rows)}</div></div>')
    return "".join(rows)


def _render_agent_code(choice) -> str:
    agent_id = _extract_agent_id(choice) if choice else ""
    if not agent_id: return EMPTY_CODE_HTML
    agent = get_agent(agent_id)
    if not agent: return '<div class="nx-empty"><div>Agent not found.</div></div>'
    code_path = Path(agent.get("code_path",""))
    agent_py  = code_path / "agent.py"
    if not agent_py.exists(): return '<div class="nx-empty"><div>agent.py not found.</div></div>'
    code     = html.escape(agent_py.read_text())
    spec     = agent.get("spec",{})
    topology = spec.get("graph_topology","?") if spec else "?"
    tools    = [t.get("name","?") for t in (spec.get("tools",[]) if spec else [])]
    return f"""
<div class="nx-panel" style="margin-bottom:12px">
  <div class="nx-panel-label">Generated source — {_esc(agent_id)}</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
    <span class="nx-badge">{_esc(topology)}</span>
    {"".join(f'<span class="nx-badge amber">{_esc(t)}</span>' for t in tools)}
    <span class="nx-badge blue">{len(agent_py.read_text().splitlines())} lines</span>
  </div>
  <div class="nx-code-block">{code}</div>
</div>"""



def run_forge(request: str):
    if not request.strip():
        viz = render_graph_svg([])
        yield (EMPTY_LOG_HTML, viz, "", _render_mission_control(),
               EMPTY_INSPECTOR_HTML, _render_lifecycle(), EMPTY_CODE_HTML,
               gr.update(choices=_agent_choices(), value=None))
        return

    accumulated_log: list[str] = []
    last_state: dict = {}

    for event in engine.forge_stream(request.strip()):
        for node_name, state_update in event.items():
            new_lines = state_update.get("build_log",[])
            for line in new_lines:
                if line not in accumulated_log:
                    accumulated_log.append(line)
            last_state.update(state_update)

            viz = render_graph_svg(accumulated_log)
            yield (
                _render_build_log(accumulated_log),
                viz,
                "",
                _render_mission_control(),
                EMPTY_INSPECTOR_HTML,
                _render_lifecycle(),
                EMPTY_CODE_HTML,
                gr.update(choices=_agent_choices(), value=None),
            )

    viz = render_graph_svg(accumulated_log)
    yield (
        _render_build_log(accumulated_log),
        viz,
        _render_deploy_result(last_state),
        _render_mission_control(),
        EMPTY_INSPECTOR_HTML,
        _render_lifecycle(),
        EMPTY_CODE_HTML,
        gr.update(choices=_agent_choices(), value=None),
    )



def inspect_agent(choice):
    agent_id = _extract_agent_id(choice)
    if not agent_id:
        return (
            EMPTY_INSPECTOR_HTML,
            EMPTY_INSPECTOR_HTML,
            "",
            render_memory_insights_html(""),
            render_memory_search_html("", ""),
        )
    return (
        _render_inspector_detail(agent_id),
        EMPTY_INSPECTOR_HTML,
        render_memory_html(agent_id),
        render_memory_insights_html(agent_id),
        render_memory_search_html(agent_id, ""),
    )

def send_task(choice, task: str):
    agent_id = _extract_agent_id(choice)
    if not agent_id or not task.strip():
        empty_search = render_memory_search_html(agent_id, "") if agent_id else ""
        empty_insights = render_memory_insights_html(agent_id) if agent_id else ""
        return '<div class="nx-task-output">No agent selected or no task provided.</div>', "", empty_insights, empty_search
    result = run_task_on_agent(agent_id, task.strip())
    out = result.get("error") and f"ERROR: {result['error']}" or result.get("stdout","") or result.get("stderr","No output")
    duration = result.get("duration_ms")
    context_note = "with memory context" if result.get("context_injected") else "without memory context"
    duration_note = f"\n\n[{duration:.0f}ms · {context_note}]" if duration is not None else ""
    return (
        f'<div class="nx-task-output">{_esc(out + duration_note)}</div>',
        render_memory_html(agent_id),
        render_memory_insights_html(agent_id),
        render_memory_search_html(agent_id, ""),
    )

def search_agent_memory(choice, query: str):
    agent_id = _extract_agent_id(choice)
    if not agent_id:
        return render_memory_search_html("", "")
    return render_memory_search_html(agent_id, query)

def ping_selected(choice):
    agent_id = _extract_agent_id(choice)
    if not agent_id: return '<div class="nx-task-output">No agent selected.</div>', ""
    result = ping_agent(agent_id)
    return f'<div class="nx-task-output">{_esc(json.dumps(result, indent=2))}</div>', ""

def restart_selected(choice):
    agent_id = _extract_agent_id(choice)
    if not agent_id: return '<div class="nx-task-output">No agent selected.</div>', _render_mission_control()
    new_pid = restart_agent(agent_id)
    return f'<div class="nx-task-output">Restarted {agent_id} → PID {new_pid}</div>', _render_mission_control()

def kill_selected(choice):
    agent_id = _extract_agent_id(choice)
    if not agent_id: return _render_mission_control(), gr.update(choices=_agent_choices(), value=None)
    stop_agent(agent_id); deregister_agent(agent_id)
    return _render_mission_control(), gr.update(choices=_agent_choices(), value=None)

def clear_agent_memory(choice):
    agent_id = _extract_agent_id(choice)
    if not agent_id: return "", render_memory_insights_html(""), render_memory_search_html("", "")
    clear_memory(agent_id)
    return render_memory_html(agent_id), render_memory_insights_html(agent_id), render_memory_search_html(agent_id, "")

def filter_mission_control(query: str, status: str, topology: str):
    return _render_mission_control(query, status, topology)

def evolve_agent(choice):
    """Generator — streams evolution progress step by step."""
    agent_id = _extract_agent_id(choice)
    if not agent_id:
        yield '<div class="nx-deploy-error">No agent selected.</div>', _render_mission_control()
        return

    agent = get_agent(agent_id)
    if not agent:
        yield '<div class="nx-deploy-error">Agent not found in registry.</div>', _render_mission_control()
        return

    mem = get_memory(agent_id)
    if len(mem) < 2:
        yield f"""<div class="nx-deploy-error" style="line-height:1.8">
  <div style="font-size:13px;margin-bottom:8px">⚠ Not enough task history to evolve.</div>
  <div style="font-size:11px;opacity:.8">This agent has {len(mem)} interaction(s).
  Run at least <strong>2 tasks</strong> in the Agent Inspector first, then try Evolve again.</div>
</div>""", _render_mission_control()
        return

    agent_name = agent.get("agent_name", agent_id)

    def _step(icon, label, detail, color="var(--cyan)"):
        return f"""<div style="display:flex;gap:12px;align-items:flex-start;padding:10px 14px;
                    border-radius:10px;background:rgba(255,255,255,0.02);border:.5px solid var(--border);
                    margin-bottom:8px">
  <div style="font-size:18px;margin-top:1px">{icon}</div>
  <div>
    <div style="font-family:var(--mono);font-size:11px;font-weight:600;color:{color}">{label}</div>
    <div style="font-family:var(--sans);font-size:11px;color:var(--muted);margin-top:2px">{detail}</div>
  </div>
</div>"""

    def _spinner_html(steps_done: str) -> str:
        return f"""<div class="nx-panel" style="margin-bottom:14px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
    <div style="font-family:var(--mono);font-size:13px;color:var(--blue)">🧬 Evolving {html.escape(agent_name)}</div>
    <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">using {len(mem)} memory interactions</div>
  </div>
  {steps_done}
  <div style="font-family:var(--mono);font-size:10px;color:var(--muted);padding:8px 0;
              animation:none;opacity:.7">⠋ working...</div>
</div>"""

    steps_html = ""

    # Step 1
    steps_html += _step("🔍", "CRITIC", f"Reviewing {len(mem)} task interactions for weaknesses...", "var(--amber)")
    yield _spinner_html(steps_html), _render_mission_control()

    # Step 2
    steps_html += _step("⚙️", "CODE GENERATOR", "Writing improved v2 based on critic directives...", "var(--amber)")
    yield _spinner_html(steps_html), _render_mission_control()

    # Step 3
    steps_html += _step("🔬", "VALIDATOR", "Running 3-stage sandbox validation on v2...", "var(--cyan)")
    yield _spinner_html(steps_html), _render_mission_control()

    # Step 4 — actually run (this is the blocking call)
    steps_html += _step("⚔️", "ARENA", "Running v1 vs v2 head-to-head benchmark...", "var(--amber)")
    yield _spinner_html(steps_html), _render_mission_control()

    # Run the actual evolution
    from meta_agents.evolution_agent import run_evolution, render_evolution_result
    result = run_evolution(agent_id)

    deployed  = result.get("deployed", False)
    v2_valid  = result.get("v2_valid", False)
    winner    = result.get("arena_winner", "?")
    message   = result.get("message", "")

    # Final step
    if result.get("error"):
        final_icon, final_label, final_color = "✗", "FAILED", "var(--red)"
    elif deployed:
        final_icon, final_label, final_color = "✓", "EVOLVED & DEPLOYED", "var(--green)"
    else:
        final_icon, final_label, final_color = "○", "COMPLETE — ORIGINAL UNCHANGED", "var(--amber)"

    steps_html += _step(final_icon, final_label, html.escape(message), final_color)

    final_html = f"""<div class="nx-panel" style="margin-bottom:14px;border-color:{final_color.replace('var(--','').replace(')','') and 'rgba(74,222,128,0.3)' if deployed else 'rgba(246,173,85,0.25)'}">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
    <div style="font-family:var(--mono);font-size:13px;color:{final_color}">🧬 {html.escape(agent_name)} Evolution Complete</div>
  </div>
  {steps_html}"""

    # Weakness summary
    weaknesses = result.get("weaknesses", [])
    directives = result.get("directives", [])
    benchmark  = result.get("benchmark", "")
    if weaknesses:
        w_html = "".join(f'<div style="font-family:var(--mono);font-size:10px;color:var(--red);padding:3px 0;border-bottom:.5px solid var(--border)">⚠ {html.escape(w)}</div>' for w in weaknesses)
        d_html = "".join(f'<div style="font-family:var(--mono);font-size:10px;color:var(--cyan);padding:3px 0;border-bottom:.5px solid var(--border)">→ {html.escape(d)}</div>' for d in directives)
        final_html += f"""
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px;margin-bottom:14px">
    <div><div class="nx-panel-label">Weaknesses found</div>{w_html}</div>
    <div><div class="nx-panel-label">Improvements applied</div>{d_html}</div>
  </div>"""
        if benchmark:
            final_html += f'<div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:4px">BENCHMARK USED</div><div style="font-family:var(--mono);font-size:10px;color:var(--amber);margin-bottom:12px">{html.escape(benchmark)}</div>'

    # Arena result
    if result.get("arena_result"):
        final_html += render_arena_result_html(result["arena_result"])

    final_html += "</div>"
    yield final_html, _render_mission_control()

def refresh_all():
    return (
        _render_mission_control(),
        _render_lifecycle(),
        gr.update(choices=_agent_choices(), value=None),
        gr.update(choices=_topology_choices(), value="all"),
        str(get_daemon_status()),
        render_analytics_html(),
    )



def run_arena_match(choice_a, choice_b, task: str):
    """Generator — shows loading state while agents run in parallel."""
    id_a = _extract_agent_id(choice_a)
    id_b = _extract_agent_id(choice_b)
    if not id_a or not id_b or id_a == id_b:
        yield '<div class="nx-deploy-error">Select two <strong>different</strong> deployed agents.</div>'
        return
    if not task.strip():
        yield '<div class="nx-deploy-error">Enter a task for both agents to run.</div>'
        return

    agent_a = get_agent(id_a)
    agent_b = get_agent(id_b)
    name_a = agent_a.get("agent_name", id_a) if agent_a else id_a
    name_b = agent_b.get("agent_name", id_b) if agent_b else id_b

    # Loading state
    yield f"""<div class="nx-panel">
  <div style="font-family:var(--mono);font-size:12px;color:var(--amber);margin-bottom:14px">
    ⚡ Arena match in progress...
  </div>
  <div style="display:flex;gap:12px;margin-bottom:16px">
    <div style="flex:1;background:var(--surface-2);border:1px solid rgba(99,179,237,0.2);border-radius:12px;padding:14px;text-align:center">
      <div style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--green-hi);margin-bottom:4px">{html.escape(name_a)}</div>
      <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">running task...</div>
    </div>
    <div style="display:flex;align-items:center;font-family:var(--mono);font-size:24px;color:var(--muted);padding:0 8px">⚔</div>
    <div style="flex:1;background:var(--surface-2);border:1px solid rgba(99,179,237,0.2);border-radius:12px;padding:14px;text-align:center">
      <div style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--green-hi);margin-bottom:4px">{html.escape(name_b)}</div>
      <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">running task...</div>
    </div>
  </div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--muted);text-align:center">
    Agents running in parallel · Judge scoring · Please wait...
  </div>
</div>"""

    result = run_arena(id_a, id_b, task.strip())
    yield render_arena_result_html(result)

def refresh_arena_history():
    results = list_arena_results()
    if not results:
        return '<div class="nx-empty"><div class="nx-empty-icon">⚔</div><div>No arena matches yet.</div></div>'
    return "".join(render_arena_result_html(r) for r in reversed(results[-5:]))



# In-memory pipeline builder state (agent IDs in order)
_pipeline_stage_ids: list[str] = []

def pipeline_add_stage(choice):
    agent_id = _extract_agent_id(choice)
    if not agent_id: return _render_pipeline_builder()
    if agent_id not in _pipeline_stage_ids:
        _pipeline_stage_ids.append(agent_id)
    return _render_pipeline_builder()

def pipeline_clear():
    _pipeline_stage_ids.clear()
    return _render_pipeline_builder()

def pipeline_remove_last():
    if _pipeline_stage_ids:
        _pipeline_stage_ids.pop()
    return _render_pipeline_builder()

def pipeline_save(name: str):
    if not name.strip() or not _pipeline_stage_ids:
        return _render_pipeline_builder(), gr.update(choices=pipeline_choices(), value=None)
    save_pipeline(name.strip(), list(_pipeline_stage_ids))
    return _render_pipeline_builder(), gr.update(choices=pipeline_choices(), value=None)

def _render_pipeline_builder() -> str:
    if not _pipeline_stage_ids:
        return '<div style="font-family:var(--mono);font-size:11px;color:var(--muted);padding:16px;text-align:center">Add agents to build a pipeline. Output of each stage becomes input to the next.</div>'
    from registry import get_agent as _ga
    stages = []
    for i, aid in enumerate(_pipeline_stage_ids):
        a = _ga(aid)
        name = a.get("agent_name", aid) if a else aid
        stages.append(f"""
<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:8px;
            background:var(--surface-2);border:.5px solid var(--border);margin-bottom:6px">
  <div style="font-family:var(--mono);font-size:11px;color:var(--cyan);min-width:20px">{i+1}</div>
  <div style="font-family:var(--mono);font-size:12px;color:var(--green-hi);flex:1">{html.escape(name)}</div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">{html.escape(aid)}</div>
  {'<div style="color:var(--muted);font-family:var(--mono);font-size:12px">→</div>' if i < len(_pipeline_stage_ids)-1 else ''}
</div>""")
    return "".join(stages)

def run_pipeline_handler(choice, task_input: str):
    """Generator — streams each stage result as it completes."""
    agent_ids = list(_pipeline_stage_ids)
    pipeline_id = None
    pipeline_name = "Ad hoc pipeline"

    # Also support loading a saved pipeline
    if choice:
        pid = _parse_choice(choice).split("—")[0].strip()
        from pipeline import get_pipeline
        pl = get_pipeline(pid)
        if pl:
            agent_ids = pl["agent_ids"]
            pipeline_id = pl["pipeline_id"]
            pipeline_name = pl["name"]

    if not agent_ids or not task_input.strip():
        yield '<div class="nx-deploy-error">No pipeline stages or no input provided.</div>', render_pipeline_runs(list_pipeline_runs())
        return

    accumulated = ""
    for stage_result in run_pipeline(agent_ids, task_input.strip(), pipeline_id=pipeline_id, pipeline_name=pipeline_name):
        accumulated += render_pipeline_stage(stage_result)
        yield accumulated, render_pipeline_runs(list_pipeline_runs())
    yield accumulated, render_pipeline_runs(list_pipeline_runs())

def refresh_saved_pipelines():
    return (
        render_saved_pipelines(list_pipelines()),
        gr.update(choices=pipeline_choices(), value=None),
        render_pipeline_runs(list_pipeline_runs()),
    )



def _load(name): return SAMPLE_REQUESTS.get(name, "")
def load_csv():   return _load("CSV Summariser")
def load_code():  return _load("Code Explainer")
def load_idea():  return _load("Idea Brainstormer")
def load_class(): return _load("Text Classifier")
def load_sql():   return _load("SQL Generator")



with gr.Blocks(css=APP_CSS, title="Nexus — Agent OS") as demo:

    with gr.Column(elem_classes="nx-shell"):
        gr.HTML(HERO_HTML)

        with gr.Tabs():

            # ── TAB 1: Forge ───────────────────────────────────────────────
            with gr.Tab("🏗  Forge"):
                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Column(elem_classes="nx-panel"):
                            gr.HTML('<div class="nx-panel-label">Load sample request</div>')
                            with gr.Row():
                                s1 = gr.Button("CSV Summariser",    size="sm")
                                s2 = gr.Button("Code Explainer",    size="sm")
                                s3 = gr.Button("Idea Brainstormer", size="sm")
                            with gr.Row():
                                s4 = gr.Button("Text Classifier", size="sm")
                                s5 = gr.Button("SQL Generator",   size="sm")
                            gr.HTML('<div style="height:1px;background:var(--border);margin:14px 0"></div>')
                            gr.HTML('<div class="nx-panel-label">Describe the agent you want</div>')
                            request_input = gr.Textbox(
                                label="", show_label=False, lines=5,
                                placeholder="e.g. Build me an agent that summarises research papers into bullet-point executive briefs...",
                            )
                            forge_btn = gr.Button("⚡  FORGE AGENT", variant="primary", size="lg")
                        gr.HTML('<div class="nx-panel-label" style="margin-top:16px">Build log</div>')
                        log_out = gr.HTML(value=EMPTY_LOG_HTML)

                    with gr.Column(scale=2):
                        gr.HTML('<div class="nx-panel-label">Live meta-graph</div>')
                        graph_viz_out = gr.HTML(value=render_graph_svg([]))
                        gr.HTML('<div class="nx-panel-label">Deploy result</div>')
                        deploy_result = gr.HTML(value="")
                        gr.HTML('<div class="nx-panel-label" style="margin-top:16px">Mission Control (live)</div>')
                        mission_side  = gr.HTML(value=_render_mission_control())

            # ── TAB 2: Mission Control ─────────────────────────────────────
            with gr.Tab("📡  Mission Control"):
                with gr.Row():
                    refresh_mc_btn = gr.Button("↺ Refresh", variant="secondary", scale=1)
                    daemon_status  = gr.Textbox(label="Monitor daemon", interactive=False, scale=2,
                                                value=str(get_daemon_status()))
                    mc_search = gr.Textbox(label="Search agents", placeholder="name, purpose, topology, id...", scale=2)
                with gr.Row():
                    mc_status = gr.Dropdown(
                        label="Status filter",
                        choices=["all", "running", "idle", "crashed", "stopped"],
                        value="all",
                        interactive=True,
                    )
                    mc_topology = gr.Dropdown(
                        label="Topology filter",
                        choices=_topology_choices(),
                        value="all",
                        interactive=True,
                    )
                mission_out = gr.HTML(value=_render_mission_control())

            # ── TAB 3: Agent Inspector ─────────────────────────────────────
            with gr.Tab("🔬  Agent Inspector"):
                with gr.Row():
                    agent_selector = gr.Dropdown(label="Select agent", choices=_agent_choices(),
                                                 value=None, interactive=True, scale=4, allow_custom_value=True)
                    refresh_insp_btn = gr.Button("↺ Refresh list", variant="secondary", scale=1)

                inspector_detail = gr.HTML(value=EMPTY_INSPECTOR_HTML)

                gr.HTML('<div class="nx-panel-label" style="margin-top:14px">Send task</div>')
                with gr.Row():
                    task_input = gr.Textbox(label="", show_label=False, lines=2,
                                            placeholder="Enter task for selected agent...", scale=4)
                    task_btn = gr.Button("▶  Run", variant="primary", scale=1)

                with gr.Row():
                    ping_btn    = gr.Button("Ping",              variant="secondary")
                    restart_btn = gr.Button("Restart",           variant="secondary")
                    evolve_btn  = gr.Button("🧬 Evolve",          variant="secondary")
                    kill_btn    = gr.Button("Kill & Deregister", variant="secondary")

                task_output = gr.HTML(value=EMPTY_INSPECTOR_HTML)

                gr.HTML('<div class="nx-panel-label" style="margin-top:14px">Session Memory</div>')
                with gr.Row():
                    clear_mem_btn = gr.Button("Clear Memory", variant="secondary", size="sm")
                    memory_search_input = gr.Textbox(label="Search memory", placeholder="keyword, topic, task snippet...", scale=3)
                    memory_search_btn = gr.Button("⌕ Search", variant="secondary", size="sm")
                with gr.Row():
                    memory_out = gr.HTML(value="")
                    memory_insights_out = gr.HTML(value="")
                gr.HTML('<div class="nx-panel-label" style="margin-top:14px">Memory Search Results</div>')
                memory_search_out = gr.HTML(value=render_memory_search_html("", ""))
                evolution_out = gr.HTML(value="")

            # ── TAB 4: Arena ───────────────────────────────────────────────
            with gr.Tab("⚔️  Arena"):
                with gr.Column(elem_classes="nx-panel"):
                    gr.HTML('<div class="nx-panel-label">Head-to-head match</div>')
                    with gr.Row():
                        refresh_arena_agents = gr.Button("↺ Refresh agents", variant="secondary", scale=1)
                    with gr.Row():
                        arena_a = gr.Dropdown(label="Agent A", choices=_agent_choices(),
                                              value=None, interactive=True, scale=2, allow_custom_value=True)
                        gr.HTML('<div style="display:flex;align-items:center;font-family:var(--mono);font-size:18px;color:var(--muted);padding:8px">⚔</div>')
                        arena_b = gr.Dropdown(label="Agent B", choices=_agent_choices(),
                                              value=None, interactive=True, scale=2, allow_custom_value=True)
                    arena_task = gr.Textbox(label="Task (same for both agents)",
                                            placeholder="e.g. Write 3 creative names for a coffee brand targeting remote workers",
                                            lines=2)
                    with gr.Row():
                        arena_btn     = gr.Button("⚡ Run Arena Match", variant="primary", scale=2)
                        refresh_arena = gr.Button("↺ Show History",    variant="secondary", scale=1)
                arena_result_out = gr.HTML(value="")

            # ── TAB 5: Pipelines ───────────────────────────────────────────
            with gr.Tab("🔗  Pipelines"):
                with gr.Row():
                    with gr.Column(scale=2):
                        with gr.Column(elem_classes="nx-panel"):
                            gr.HTML('<div class="nx-panel-label">Build pipeline</div>')
                            with gr.Row():
                                pipeline_agent_add = gr.Dropdown(
                                    label="Add agent to pipeline",
                                    choices=_agent_choices(), value=None,
                                    interactive=True, scale=3, allow_custom_value=True,
                                )
                                refresh_pl_agents  = gr.Button("↺", variant="secondary", scale=1)
                                add_stage_btn      = gr.Button("+ Add", variant="primary", scale=1)
                            with gr.Row():
                                remove_btn = gr.Button("− Remove Last", variant="secondary")
                                clear_btn  = gr.Button("✕ Clear All",   variant="secondary")
                            pipeline_builder_out = gr.HTML(value=_render_pipeline_builder())
                            gr.HTML('<div style="height:1px;background:var(--border);margin:12px 0"></div>')
                            with gr.Row():
                                pipeline_name = gr.Textbox(label="Pipeline name", placeholder="e.g. Research → Summary → Email", scale=3)
                                save_pl_btn   = gr.Button("💾 Save", variant="secondary", scale=1)

                            gr.HTML('<div class="nx-panel-label" style="margin-top:12px">Or load saved pipeline</div>')
                            with gr.Row():
                                saved_pl_selector = gr.Dropdown(
                                    label="Saved pipelines", choices=pipeline_choices(),
                                    value=None, interactive=True, scale=3, allow_custom_value=True,
                                )
                                refresh_pl_btn = gr.Button("↺", variant="secondary", scale=1)

                        gr.HTML('<div class="nx-panel-label" style="margin-top:14px">Saved pipelines</div>')
                        saved_pl_out = gr.HTML(value=render_saved_pipelines(list_pipelines()))
                        gr.HTML('<div class="nx-panel-label" style="margin-top:14px">Recent pipeline runs</div>')
                        pipeline_runs_out = gr.HTML(value=render_pipeline_runs(list_pipeline_runs()))

                    with gr.Column(scale=2):
                        with gr.Column(elem_classes="nx-panel"):
                            gr.HTML('<div class="nx-panel-label">Run pipeline</div>')
                            pipeline_input = gr.Textbox(label="Initial input", lines=3,
                                                        placeholder="The input that flows through all stages...")
                            run_pl_btn = gr.Button("▶  Run Pipeline", variant="primary", size="lg")
                        gr.HTML('<div class="nx-panel-label" style="margin-top:14px">Pipeline execution</div>')
                        pipeline_output = gr.HTML(value="")

            # ── TAB 6: Lifecycle ───────────────────────────────────────────
            with gr.Tab("📊  Lifecycle"):
                refresh_lc_btn = gr.Button("↺ Refresh timeline", variant="secondary")
                lifecycle_out  = gr.HTML(value=_render_lifecycle())

            # ── TAB 7: Analytics ──────────────────────────────────────────
            with gr.Tab("🛰  Analytics"):
                refresh_analytics_btn = gr.Button("↺ Refresh analytics", variant="secondary")
                analytics_out = gr.HTML(value=render_analytics_html())

            # ── TAB 8: Source Code ─────────────────────────────────────────
            with gr.Tab("🧬  Source Code"):
                with gr.Row():
                    code_selector = gr.Dropdown(label="Select agent to view code",
                                                choices=_agent_choices(), value=None,
                                                interactive=True, scale=4, allow_custom_value=True)
                    refresh_code_btn = gr.Button("↺ Refresh list", variant="secondary", scale=1)
                code_out = gr.HTML(value=EMPTY_CODE_HTML)

    # ── Forge wiring ──────────────────────────────────────────────────────────
    forge_btn.click(
        fn=run_forge,
        inputs=[request_input],
        outputs=[log_out, graph_viz_out, deploy_result, mission_side,
                 task_output, lifecycle_out, code_out, agent_selector],
    )
    forge_btn.click(fn=render_analytics_html, outputs=[analytics_out])
    forge_btn.click(fn=_refresh_topology_dropdown, outputs=[mc_topology])
    # After forge, also refresh arena + pipeline agent selectors
    forge_btn.click(
        fn=_refresh_all_selectors,
        outputs=[arena_a, arena_b, pipeline_agent_add, code_selector, agent_selector],
    )
    s1.click(fn=load_csv,   outputs=[request_input])
    s2.click(fn=load_code,  outputs=[request_input])
    s3.click(fn=load_idea,  outputs=[request_input])
    s4.click(fn=load_class, outputs=[request_input])
    s5.click(fn=load_sql,   outputs=[request_input])

    # ── Mission Control ───────────────────────────────────────────────────────
    refresh_mc_btn.click(fn=refresh_all,
                         outputs=[mission_out, lifecycle_out, agent_selector, mc_topology, daemon_status, analytics_out])
    mc_search.change(fn=filter_mission_control, inputs=[mc_search, mc_status, mc_topology], outputs=[mission_out])
    mc_status.change(fn=filter_mission_control, inputs=[mc_search, mc_status, mc_topology], outputs=[mission_out])
    mc_topology.change(fn=filter_mission_control, inputs=[mc_search, mc_status, mc_topology], outputs=[mission_out])

    # ── Inspector ─────────────────────────────────────────────────────────────
    agent_selector.change(fn=inspect_agent, inputs=[agent_selector],
                          outputs=[inspector_detail, task_output, memory_out, memory_insights_out, memory_search_out])
    refresh_insp_btn.click(fn=_refresh_dropdown, outputs=[agent_selector])
    task_btn.click(fn=send_task, inputs=[agent_selector, task_input],
                   outputs=[task_output, memory_out, memory_insights_out, memory_search_out])
    ping_btn.click(fn=ping_selected, inputs=[agent_selector],
                   outputs=[task_output, memory_out])
    restart_btn.click(fn=restart_selected, inputs=[agent_selector],
                      outputs=[task_output, mission_out])
    evolve_btn.click(fn=evolve_agent, inputs=[agent_selector],
                     outputs=[evolution_out, mission_out])
    kill_btn.click(fn=kill_selected, inputs=[agent_selector],
                   outputs=[mission_out, agent_selector])
    clear_mem_btn.click(fn=clear_agent_memory, inputs=[agent_selector],
                        outputs=[memory_out, memory_insights_out, memory_search_out])
    memory_search_btn.click(fn=search_agent_memory, inputs=[agent_selector, memory_search_input],
                            outputs=[memory_search_out])
    memory_search_input.submit(fn=search_agent_memory, inputs=[agent_selector, memory_search_input],
                               outputs=[memory_search_out])

    # ── Arena ─────────────────────────────────────────────────────────────────
    refresh_arena_agents.click(fn=_refresh_dropdown, outputs=[arena_a])
    refresh_arena_agents.click(fn=_refresh_dropdown, outputs=[arena_b])
    arena_btn.click(fn=run_arena_match, inputs=[arena_a, arena_b, arena_task],
                    outputs=[arena_result_out])
    refresh_arena.click(fn=refresh_arena_history, outputs=[arena_result_out])

    # ── Pipelines ─────────────────────────────────────────────────────────────
    refresh_pl_agents.click(fn=_refresh_dropdown, outputs=[pipeline_agent_add])
    add_stage_btn.click(fn=pipeline_add_stage, inputs=[pipeline_agent_add],
                        outputs=[pipeline_builder_out])
    remove_btn.click(fn=pipeline_remove_last, outputs=[pipeline_builder_out])
    clear_btn.click(fn=pipeline_clear,        outputs=[pipeline_builder_out])
    save_pl_btn.click(fn=pipeline_save, inputs=[pipeline_name],
                      outputs=[pipeline_builder_out, saved_pl_selector])
    refresh_pl_btn.click(fn=refresh_saved_pipelines,
                         outputs=[saved_pl_out, saved_pl_selector, pipeline_runs_out])
    run_pl_btn.click(fn=run_pipeline_handler,
                     inputs=[saved_pl_selector, pipeline_input],
                     outputs=[pipeline_output, pipeline_runs_out])

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    refresh_lc_btn.click(fn=_render_lifecycle, outputs=[lifecycle_out])

    # ── Analytics ─────────────────────────────────────────────────────────────
    refresh_analytics_btn.click(fn=render_analytics_html, outputs=[analytics_out])

    # ── Code viewer ───────────────────────────────────────────────────────────
    code_selector.change(fn=_render_agent_code, inputs=[code_selector], outputs=[code_out])
    refresh_code_btn.click(fn=_refresh_dropdown, outputs=[code_selector])

    # ── On page load ──────────────────────────────────────────────────────────
    demo.load(fn=_render_mission_control, outputs=[mission_out])
    demo.load(fn=_render_lifecycle,       outputs=[lifecycle_out])
    demo.load(fn=_refresh_dropdown,       outputs=[agent_selector])
    demo.load(fn=_refresh_dropdown,       outputs=[code_selector])
    demo.load(fn=_refresh_dropdown,       outputs=[arena_a])
    demo.load(fn=_refresh_dropdown,       outputs=[arena_b])
    demo.load(fn=_refresh_dropdown,       outputs=[pipeline_agent_add])
    demo.load(fn=_refresh_topology_dropdown, outputs=[mc_topology])
    demo.load(fn=render_analytics_html,   outputs=[analytics_out])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861, share=False)