"""
Nexus — Pipeline Builder
Chain deployed agents sequentially: Agent A output → Agent B input → Agent C input...
Pipelines are named, saved, and reloadable.
"""
import json
import time
import uuid
import html as _html
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from config import MEMORY_DIR
from registry import run_task_on_agent, get_agent

PIPELINES_FILE = MEMORY_DIR / "pipelines.json"
PIPELINE_RUNS_FILE = MEMORY_DIR / "pipeline_runs.json"


# ── Pipeline CRUD ──────────────────────────────────────────────────────────────

def save_pipeline(name: str, agent_ids: list[str]) -> dict:
    pipelines = _load_all()
    pid = uuid.uuid4().hex[:8]
    record = {
        "pipeline_id":  pid,
        "name":         name,
        "agent_ids":    agent_ids,
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "run_count":    0,
    }
    pipelines[pid] = record
    _save_all(pipelines)
    return record


def list_pipelines() -> list[dict]:
    return list(_load_all().values())


def get_pipeline(pipeline_id: str) -> dict | None:
    return _load_all().get(pipeline_id)


def delete_pipeline(pipeline_id: str) -> bool:
    pipelines = _load_all()
    if pipeline_id in pipelines:
        del pipelines[pipeline_id]
        _save_all(pipelines)
        return True
    return False


def list_pipeline_runs(limit: int | None = 12, pipeline_id: str | None = None) -> list[dict]:
    runs = _load_pipeline_runs()
    if pipeline_id:
        runs = [run for run in runs if run.get("pipeline_id") == pipeline_id]
    if limit is not None:
        return runs[-limit:]
    return runs


def _load_all() -> dict:
    if PIPELINES_FILE.exists():
        try:
            return json.loads(PIPELINES_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_all(pipelines: dict) -> None:
    PIPELINES_FILE.write_text(json.dumps(pipelines, indent=2))


def _load_pipeline_runs() -> list[dict]:
    if PIPELINE_RUNS_FILE.exists():
        try:
            return json.loads(PIPELINE_RUNS_FILE.read_text())
        except Exception:
            pass
    return []


def _save_pipeline_runs(runs: list[dict]) -> None:
    PIPELINE_RUNS_FILE.write_text(json.dumps(runs[-60:], indent=2))


# ── Pipeline execution ─────────────────────────────────────────────────────────

def run_pipeline(
    agent_ids: list[str],
    initial_input: str,
    pipeline_id: str | None = None,
    pipeline_name: str | None = None,
) -> Generator[dict, None, None]:
    """
    Generator that runs agents sequentially, yielding after each stage.
    Each stage's output becomes the next stage's input.

    Yields dicts:
      {"stage": int, "agent_id": str, "input": str, "output": str,
       "success": bool, "error": str|None}
    """
    current_input = initial_input
    total = len(agent_ids)
    started_at = datetime.now(timezone.utc).isoformat()
    stage_results: list[dict] = []

    for i, agent_id in enumerate(agent_ids):
        stage_num = i + 1
        agent = get_agent(agent_id)
        agent_name = agent.get("agent_name", agent_id) if agent else agent_id

        stage_started = time.perf_counter()
        result = run_task_on_agent(agent_id, current_input)
        duration_ms = round((time.perf_counter() - stage_started) * 1000, 1)

        if result.get("error"):
            stage_result = {
                "stage":      stage_num,
                "total":      total,
                "agent_id":   agent_id,
                "agent_name": agent_name,
                "input":      current_input[:300],
                "output":     "",
                "success":    False,
                "error":      result["error"],
                "duration_ms": duration_ms,
            }
            stage_results.append(stage_result)
            _record_pipeline_run(
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name or "Ad hoc pipeline",
                initial_input=initial_input,
                stage_results=stage_results,
                started_at=started_at,
            )
            yield stage_result
            return   # Stop pipeline on error

        output = result.get("stdout", "") or result.get("stderr", "")
        stage_result = {
            "stage":      stage_num,
            "total":      total,
            "agent_id":   agent_id,
            "agent_name": agent_name,
            "input":      current_input[:300],
            "output":     output,
            "success":    True,
            "error":      None,
            "duration_ms": result.get("duration_ms", duration_ms),
        }
        stage_results.append(stage_result)
        yield stage_result
        current_input = output   # Chain: output → next input

    _record_pipeline_run(
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name or "Ad hoc pipeline",
        initial_input=initial_input,
        stage_results=stage_results,
        started_at=started_at,
    )


def pipeline_choices() -> list[str]:
    pls = list_pipelines()
    return [f"{p['pipeline_id']} — {p['name']} ({len(p['agent_ids'])} agents)"
            for p in pls] or []


# ── HTML rendering ─────────────────────────────────────────────────────────────

def render_pipeline_stage(stage_result: dict) -> str:
    """Render a single completed pipeline stage as HTML."""
    stage     = stage_result.get("stage", "?")
    total     = stage_result.get("total", "?")
    name      = _html.escape(stage_result.get("agent_name", "?"))
    inp       = _html.escape(stage_result.get("input", "")[:200])
    out       = _html.escape(stage_result.get("output", "")[:400])
    success   = stage_result.get("success", False)
    error     = stage_result.get("error", "")
    duration  = stage_result.get("duration_ms", 0)

    color  = "var(--green)" if success else "var(--red)"
    icon   = "✓" if success else "✗"
    border = "rgba(74,222,128,0.25)" if success else "rgba(248,113,113,0.25)"

    error_html = f'<div style="color:var(--red);font-family:var(--mono);font-size:10px;margin-top:6px">ERROR: {_html.escape(str(error))}</div>' if error else ""

    return f"""
<div style="display:grid;grid-template-columns:36px 1fr;gap:12px;align-items:start;margin-bottom:10px">
  <div style="text-align:center">
    <div style="width:34px;height:34px;border-radius:50%;border:1.5px solid {color};
                display:flex;align-items:center;justify-content:center;
                font-family:var(--mono);font-size:11px;color:{color};background:var(--surface)">{stage}</div>
    {'<div style="width:1px;height:calc(100% - 36px);background:var(--border);margin:4px auto 0"></div>' if stage < total else ''}
  </div>
  <div style="background:var(--surface-2);border:1px solid {border};border-radius:12px;padding:12px 14px;min-height:60px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
      <div style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--green-hi)">{name}</div>
      <span style="font-family:var(--mono);font-size:10px;color:{color}">{icon} Stage {stage}/{total} · {duration:.0f}ms</span>
    </div>
    <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:3px">INPUT →</div>
    <div style="font-family:var(--mono);font-size:10px;color:var(--amber);margin-bottom:8px;line-height:1.4">{inp}</div>
    <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:3px">OUTPUT →</div>
    <div style="font-family:var(--mono);font-size:10px;color:var(--green-hi);line-height:1.5;white-space:pre-wrap">{out}</div>
    {error_html}
  </div>
</div>"""


def render_saved_pipelines(pipelines: list[dict]) -> str:
    if not pipelines:
        return '<div style="font-family:var(--mono);font-size:11px;color:var(--muted);padding:16px;text-align:center">No saved pipelines yet.</div>'

    from registry import get_agent
    rows = []
    for p in sorted(pipelines, key=lambda x: x.get("created_at",""), reverse=True):
        names = []
        for aid in p.get("agent_ids", []):
            a = get_agent(aid)
            names.append(a.get("agent_name", aid) if a else aid)
        chain = " → ".join(f'<span style="color:var(--green)">{_html.escape(n)}</span>' for n in names)
        rows.append(f"""
<div style="padding:12px 14px;border-radius:10px;background:var(--surface-2);
            border:.5px solid var(--border);margin-bottom:8px">
  <div style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--text);margin-bottom:4px">{_html.escape(p['name'])}</div>
  <div style="font-size:11px;line-height:1.6">{chain}</div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-top:4px">
    {len(p['agent_ids'])} agents · {p.get('run_count',0)} runs · {p.get('created_at','')[:10]}
  </div>
</div>""")
    return "".join(rows)


def render_pipeline_runs(runs: list[dict]) -> str:
    if not runs:
        return '<div style="font-family:var(--mono);font-size:11px;color:var(--muted);padding:16px;text-align:center">No pipeline runs yet.</div>'

    rows = []
    for run in reversed(runs):
        success = run.get("success", False)
        color = "var(--green)" if success else "var(--red)"
        status = "SUCCESS" if success else "FAILED"
        stages = run.get("stages", [])
        stage_html = "".join(
            f'<div style="display:flex;justify-content:space-between;gap:12px;font-family:var(--mono);font-size:10px;color:var(--muted);padding:3px 0">'
            f'<span>{_html.escape(stage.get("agent_name", stage.get("agent_id", "?")))}</span>'
            f'<span style="color:{color if stage.get("success") else "var(--red)"}">{stage.get("duration_ms", 0):.0f}ms</span>'
            f'</div>'
            for stage in stages[:5]
        )
        rows.append(f"""
<div style="padding:12px 14px;border-radius:10px;background:var(--surface-2);
            border:.5px solid var(--border);margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:6px">
    <div style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--text)">{_html.escape(run.get('pipeline_name', 'Pipeline run'))}</div>
    <div style="font-family:var(--mono);font-size:9px;color:{color}">{status} · {run.get('duration_ms', 0):.0f}ms</div>
  </div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:8px">
    {run.get('finished_at', '')[:16].replace('T', ' ')} · {run.get('stage_count', 0)} stages
  </div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--amber);line-height:1.5;margin-bottom:8px">{_html.escape(run.get('input_preview', ''))}</div>
  {stage_html}
</div>""")
    return "".join(rows)


def _record_pipeline_run(
    pipeline_id: str | None,
    pipeline_name: str,
    initial_input: str,
    stage_results: list[dict],
    started_at: str,
) -> None:
    finished_at = datetime.now(timezone.utc).isoformat()
    duration_ms = sum(stage.get("duration_ms", 0) for stage in stage_results)
    success = bool(stage_results) and all(stage.get("success") for stage in stage_results)
    run_record = {
        "run_id": uuid.uuid4().hex[:8],
        "pipeline_id": pipeline_id or "adhoc",
        "pipeline_name": pipeline_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round(duration_ms, 1),
        "success": success,
        "stage_count": len(stage_results),
        "input_preview": initial_input[:180],
        "stages": [
            {
                "stage": stage.get("stage"),
                "agent_id": stage.get("agent_id"),
                "agent_name": stage.get("agent_name"),
                "success": stage.get("success"),
                "duration_ms": stage.get("duration_ms", 0),
                "error": stage.get("error"),
            }
            for stage in stage_results
        ],
    }

    runs = _load_pipeline_runs()
    runs.append(run_record)
    _save_pipeline_runs(runs)

    if pipeline_id:
        pipelines = _load_all()
        if pipeline_id in pipelines:
            pipelines[pipeline_id]["run_count"] = pipelines[pipeline_id].get("run_count", 0) + 1
            pipelines[pipeline_id]["last_run_at"] = finished_at
            _save_all(pipelines)