"""
Nexus — Analytics helpers
Renders cross-system metrics, rankings, and recent activity snapshots.
"""
import html
from collections import Counter

from arena import list_arena_results
from memory_store import memory_stats
from pipeline import list_pipeline_runs, list_pipelines
from registry import list_agents


def render_analytics_html() -> str:
    agents = list_agents()
    arena_results = list_arena_results()
    pipelines = list_pipelines()
    pipeline_runs = list_pipeline_runs(limit=8)

    if not agents and not arena_results and not pipeline_runs:
        return """<div class="nx-empty">
  <div class="nx-empty-icon">⬡</div>
  <div>No analytics yet.</div>
  <div style="margin-top:5px;opacity:0.6">Forge agents, run tasks, and benchmark them to unlock the command center.</div>
</div>"""

    total_tasks = sum(agent.get("task_count", 0) for agent in agents)
    total_memories = sum(memory_stats(agent["agent_id"]).get("entry_count", 0) for agent in agents)
    evolved_agents = sum(1 for agent in agents if agent.get("version", 1) > 1)
    topologies = Counter(
        (agent.get("spec", {}) or {}).get("graph_topology", "unknown") for agent in agents
    )

    metrics_html = f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:14px">
  {_metric_card(len(agents), 'Agents', 'var(--green-hi)')}
  {_metric_card(total_tasks, 'Tasks run', 'var(--amber)')}
  {_metric_card(total_memories, 'Memory turns', 'var(--blue)')}
  {_metric_card(len(arena_results), 'Arena matches', 'var(--cyan)')}
  {_metric_card(evolved_agents, 'Evolved', 'var(--purple)')}
</div>"""

    topology_html = "".join(
        f"""
<div style="padding:10px 12px;border-radius:10px;background:var(--surface-2);border:.5px solid var(--border)">
  <div style="display:flex;justify-content:space-between;gap:10px;font-family:var(--mono);font-size:10px;color:var(--muted);margin-bottom:6px">
    <span>{html.escape(name.upper())}</span><span>{count}</span>
  </div>
  <div style="height:6px;border-radius:999px;background:rgba(255,255,255,0.06);overflow:hidden">
    <div style="width:{(count / max(len(agents), 1)) * 100:.0f}%;height:100%;background:var(--green)"></div>
  </div>
</div>"""
        for name, count in sorted(topologies.items(), key=lambda item: (-item[1], item[0]))
    ) or '<div style="font-family:var(--mono);font-size:10px;color:var(--muted)">No topology data yet.</div>'

    leaderboard = sorted(
        agents,
        key=lambda agent: (
            agent.get("arena", {}).get("wins", 0),
            agent.get("task_count", 0),
            agent.get("version", 1),
        ),
        reverse=True,
    )[:5]
    leaderboard_html = "".join(
        f"""
<div style="display:grid;grid-template-columns:36px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-bottom:.5px solid var(--border)">
  <div style="font-family:var(--mono);font-size:14px;color:var(--amber)">#{idx}</div>
  <div>
    <div style="font-family:var(--mono);font-size:11px;color:var(--text)">{html.escape(agent.get('agent_name', agent['agent_id']))}</div>
    <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">{html.escape(agent['agent_id'])}</div>
  </div>
  <div style="text-align:right;font-family:var(--mono);font-size:10px;color:var(--green-hi)">
    {agent.get('arena', {}).get('wins', 0)}W · {agent.get('task_count', 0)}T
  </div>
</div>"""
        for idx, agent in enumerate(leaderboard, start=1)
    ) or '<div style="font-family:var(--mono);font-size:10px;color:var(--muted)">No ranked agents yet.</div>'

    recent_events = _recent_events(agents, pipeline_runs)
    recent_events_html = "".join(
        f"""
<div style="display:grid;grid-template-columns:86px 1fr;gap:10px;padding:8px 0;border-bottom:.5px solid var(--border)">
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);text-align:right">{event['timestamp']}</div>
  <div style="font-family:var(--mono);font-size:10px;color:{event['color']}">{html.escape(event['label'])}</div>
</div>"""
        for event in recent_events
    ) or '<div style="font-family:var(--mono);font-size:10px;color:var(--muted)">No recent events yet.</div>'

    pipeline_html = "".join(
        f"""
<div style="padding:10px 0;border-bottom:.5px solid var(--border)">
  <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:4px">
    <div style="font-family:var(--mono);font-size:11px;color:var(--text)">{html.escape(run.get('pipeline_name', 'Pipeline'))}</div>
    <div style="font-family:var(--mono);font-size:9px;color:{'var(--green)' if run.get('success') else 'var(--red)'}">{'OK' if run.get('success') else 'FAIL'}</div>
  </div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">{run.get('finished_at', '')[:16].replace('T', ' ')} · {run.get('duration_ms', 0):.0f}ms</div>
</div>"""
        for run in reversed(pipeline_runs[-4:])
    ) or '<div style="font-family:var(--mono);font-size:10px;color:var(--muted)">No pipeline runs yet.</div>'

    saved_pipeline_count = len(pipelines)

    return f"""
{metrics_html}
<div style="display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-bottom:14px">
  <div class="nx-panel">
    <div class="nx-panel-label">System topology mix</div>
    <div style="display:grid;gap:8px">{topology_html}</div>
  </div>
  <div class="nx-panel">
    <div class="nx-panel-label">Arena leaderboard</div>
    {leaderboard_html}
  </div>
</div>
<div style="display:grid;grid-template-columns:1.1fr 1fr 0.9fr;gap:14px">
  <div class="nx-panel">
    <div class="nx-panel-label">Recent activity</div>
    {recent_events_html}
  </div>
  <div class="nx-panel">
    <div class="nx-panel-label">Workflow telemetry</div>
    <div style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-bottom:10px">{saved_pipeline_count} saved pipelines</div>
    {pipeline_html}
  </div>
  <div class="nx-panel">
    <div class="nx-panel-label">Recommended next upgrades</div>
    <div style="font-family:var(--mono);font-size:10px;color:var(--amber);line-height:1.8">
      <div>1. Agent skill tags + semantic search</div>
      <div>2. Forge presets by domain</div>
      <div>3. Live streaming stdout for long tasks</div>
      <div>4. Pipeline branching and merge stages</div>
      <div>5. Exportable benchmark reports</div>
    </div>
  </div>
</div>"""


def _metric_card(value: int, label: str, color: str) -> str:
    return f"""
<div class="nx-metric" style="padding:12px">
  <div class="nx-metric-val" style="color:{color}">{value}</div>
  <div class="nx-metric-lbl">{html.escape(label)}</div>
</div>"""


def _recent_events(agents: list[dict], pipeline_runs: list[dict]) -> list[dict]:
    events = []
    for agent in agents:
        if agent.get("deploy_timestamp"):
            events.append({
                "timestamp": agent["deploy_timestamp"][5:16].replace("T", " "),
                "label": f"Deployed {agent.get('agent_name', agent['agent_id'])}",
                "color": "var(--green)",
            })
        if agent.get("last_task_at"):
            events.append({
                "timestamp": agent["last_task_at"][5:16].replace("T", " "),
                "label": f"Task completed on {agent.get('agent_name', agent['agent_id'])}",
                "color": "var(--amber)",
            })
        if agent.get("evolved_at"):
            events.append({
                "timestamp": agent["evolved_at"][5:16].replace("T", " "),
                "label": f"Evolved {agent.get('agent_name', agent['agent_id'])} to v{agent.get('version', 1)}",
                "color": "var(--purple)",
            })

    for run in pipeline_runs:
        if run.get("finished_at"):
            events.append({
                "timestamp": run["finished_at"][5:16].replace("T", " "),
                "label": f"Pipeline run finished: {run.get('pipeline_name', 'Pipeline')}",
                "color": "var(--blue)",
            })

    events.sort(key=lambda event: event["timestamp"], reverse=True)
    return events[:8]