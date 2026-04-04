"""
Nexus — Session Memory Store
Each deployed agent gets a rolling memory of its task history.
When a task runs, the last N interactions are injected as context.
Memory is persisted to memory/sessions/{agent_id}.json.
"""
import json
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from config import MEMORY_DIR

SESSIONS_DIR = MEMORY_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

MAX_MEMORY_ENTRIES = 20    # per agent
CONTEXT_WINDOW     = 5     # how many recent entries to inject into task

_lock = threading.Lock()

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "if", "in", "into", "is", "it", "of", "on", "or", "that", "the",
    "their", "them", "there", "this", "to", "was", "we", "with", "you",
    "your",
}


def _session_path(agent_id: str) -> Path:
    return SESSIONS_DIR / f"{agent_id}.json"


def _load_session(agent_id: str) -> list:
    path = _session_path(agent_id)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return []


def _save_session(agent_id: str, entries: list) -> None:
    _session_path(agent_id).write_text(json.dumps(entries, indent=2))


def add_memory(agent_id: str, task: str, output: str) -> None:
    """Record a task/output pair into the agent's memory."""
    with _lock:
        entries = _load_session(agent_id)
        entries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task":      task[:500],
            "output":    output[:1000],
        })
        # Rolling window — keep only the last MAX_MEMORY_ENTRIES
        if len(entries) > MAX_MEMORY_ENTRIES:
            entries = entries[-MAX_MEMORY_ENTRIES:]
        _save_session(agent_id, entries)


def get_memory(agent_id: str) -> list:
    """Return all memory entries for an agent."""
    with _lock:
        return _load_session(agent_id)


def get_context_block(agent_id: str) -> str:
    """
    Return a formatted context string of the last CONTEXT_WINDOW interactions.
    Injected into the agent's task call to give it memory.
    """
    entries = get_memory(agent_id)
    if not entries:
        return ""
    recent = entries[-CONTEXT_WINDOW:]
    lines = ["[MEMORY — your recent task history]"]
    for e in recent:
        ts = e.get("timestamp", "")[:16].replace("T", " ")
        lines.append(f"[{ts}] Task: {e['task']}")
        lines.append(f"         Output: {e['output'][:200]}")
    lines.append("[END MEMORY]")
    return "\n".join(lines)


def clear_memory(agent_id: str) -> None:
    """Wipe all memory for an agent."""
    with _lock:
        _save_session(agent_id, [])


def memory_stats(agent_id: str) -> dict:
    """Return stats about an agent's memory."""
    entries = get_memory(agent_id)
    return {
        "entry_count":   len(entries),
        "max_entries":   MAX_MEMORY_ENTRIES,
        "oldest":        entries[0]["timestamp"][:16] if entries else None,
        "newest":        entries[-1]["timestamp"][:16] if entries else None,
        "total_chars":   sum(len(e["task"]) + len(e["output"]) for e in entries),
    }


def search_memory(agent_id: str, query: str, limit: int = 8) -> list[dict]:
    """Return recent memory entries matching a simple case-insensitive query."""
    needle = (query or "").strip().lower()
    entries = list(reversed(get_memory(agent_id)))
    if not needle:
        return entries[:limit]

    matches = []
    for entry in entries:
        haystack = f"{entry.get('task', '')}\n{entry.get('output', '')}".lower()
        if needle in haystack:
            matches.append(entry)
        if len(matches) >= limit:
            break
    return matches


def memory_digest(agent_id: str) -> dict:
    """Compute lightweight memory insights without requiring an LLM."""
    entries = get_memory(agent_id)
    if not entries:
        return {
            "entry_count": 0,
            "avg_output_chars": 0,
            "top_keywords": [],
            "latest_task": "",
            "latest_timestamp": "",
        }

    token_counter: Counter[str] = Counter()
    for entry in entries:
        text = f"{entry.get('task', '')} {entry.get('output', '')}"
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()):
            if token not in _STOPWORDS:
                token_counter[token] += 1

    latest = entries[-1]
    avg_output_chars = int(sum(len(e.get("output", "")) for e in entries) / len(entries))
    return {
        "entry_count": len(entries),
        "avg_output_chars": avg_output_chars,
        "top_keywords": [word for word, _ in token_counter.most_common(5)],
        "latest_task": latest.get("task", "")[:80],
        "latest_timestamp": latest.get("timestamp", "")[:16].replace("T", " "),
    }


def render_memory_html(agent_id: str) -> str:
    """Render the memory panel HTML for the Inspector tab."""
    entries = get_memory(agent_id)
    stats   = memory_stats(agent_id)

    if not entries:
        return """<div style="font-family:var(--mono);font-size:11px;color:var(--muted);
                              padding:16px;text-align:center">
            No memory yet — run tasks to build context.</div>"""

    count     = stats["entry_count"]
    total_ch  = stats["total_chars"]
    newest    = stats["newest"] or ""

    header = f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">
  <div class="nx-metric" style="padding:10px">
    <div class="nx-metric-val" style="font-size:20px">{count}</div>
    <div class="nx-metric-lbl">Interactions</div>
  </div>
  <div class="nx-metric" style="padding:10px">
    <div class="nx-metric-val" style="font-size:20px;color:var(--amber)">{total_ch:,}</div>
    <div class="nx-metric-lbl">Chars stored</div>
  </div>
  <div class="nx-metric" style="padding:10px">
    <div class="nx-metric-val" style="font-size:14px;color:var(--cyan)">{newest}</div>
    <div class="nx-metric-lbl">Last entry</div>
  </div>
</div>"""

    import html as _html
    rows = []
    for e in reversed(entries[-10:]):     # show newest first, max 10
        ts  = e.get("timestamp", "")[:16].replace("T", " ")
        t   = _html.escape(e.get("task", "")[:120])
        out = _html.escape(e.get("output", "")[:200])
        rows.append(f"""
<div style="padding:10px 12px;border-radius:8px;background:rgba(255,255,255,0.02);
            border:.5px solid var(--border);margin-bottom:6px">
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:4px">{ts}</div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--amber);margin-bottom:3px">▶ {t}</div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--green-hi);
              line-height:1.5;white-space:pre-wrap">{out}</div>
</div>""")

    return header + "".join(rows)


def render_memory_search_html(agent_id: str, query: str) -> str:
    """Render keyword-based search results for an agent's memory."""
    import html as _html

    query = (query or "").strip()
    if not query:
        return """<div style="font-family:var(--mono);font-size:10px;color:var(--muted);
                              padding:12px;border:.5px dashed var(--border);border-radius:8px">
            Search memory by keyword to jump to previous tasks, outputs, or recurring topics.</div>"""

    matches = search_memory(agent_id, query)
    if not matches:
        return f"""<div style="font-family:var(--mono);font-size:10px;color:var(--muted);
                              padding:12px;border:.5px dashed var(--border);border-radius:8px">
            No memory matches found for "{_html.escape(query)}".</div>"""

    rows = []
    for entry in matches:
        ts = entry.get("timestamp", "")[:16].replace("T", " ")
        task = _html.escape(entry.get("task", "")[:140])
        output = _html.escape(entry.get("output", "")[:220])
        rows.append(f"""
<div style="padding:10px 12px;border-radius:8px;background:rgba(255,255,255,0.02);
            border:.5px solid var(--border);margin-bottom:6px">
  <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:4px">
    <div style="font-family:var(--mono);font-size:9px;color:var(--cyan)">MATCH</div>
    <div style="font-family:var(--mono);font-size:9px;color:var(--muted)">{ts}</div>
  </div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--amber);margin-bottom:4px">▶ {task}</div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--green-hi);line-height:1.5;white-space:pre-wrap">{output}</div>
</div>""")

    return "".join(rows)


def render_memory_insights_html(agent_id: str) -> str:
    """Render summary insights for an agent's accumulated memory."""
    digest = memory_digest(agent_id)
    if digest["entry_count"] == 0:
        return """<div style="font-family:var(--mono);font-size:10px;color:var(--muted);
                              padding:12px;border:.5px dashed var(--border);border-radius:8px">
            No memory insights yet. Run a task to start building a behavioral profile.</div>"""

    keywords = digest["top_keywords"] or ["none yet"]
    keyword_html = "".join(
        f'<span class="nx-badge blue" style="margin-right:6px;margin-bottom:6px;display:inline-block">{word}</span>'
        for word in keywords
    )
    latest_task = digest["latest_task"] or "N/A"

    return f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px">
  <div class="nx-metric" style="padding:10px">
    <div class="nx-metric-val" style="font-size:18px">{digest['entry_count']}</div>
    <div class="nx-metric-lbl">Stored turns</div>
  </div>
  <div class="nx-metric" style="padding:10px">
    <div class="nx-metric-val" style="font-size:18px;color:var(--blue)">{digest['avg_output_chars']}</div>
    <div class="nx-metric-lbl">Avg output chars</div>
  </div>
  <div class="nx-metric" style="padding:10px">
    <div class="nx-metric-val" style="font-size:12px;color:var(--cyan)">{digest['latest_timestamp'] or 'N/A'}</div>
    <div class="nx-metric-lbl">Last activity</div>
  </div>
</div>
<div style="padding:12px;border-radius:10px;background:rgba(255,255,255,0.02);border:.5px solid var(--border)">
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:8px">Recurring keywords</div>
  <div style="margin-bottom:10px">{keyword_html}</div>
  <div style="font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:4px">Latest task</div>
  <div style="font-family:var(--mono);font-size:10px;color:var(--amber);line-height:1.5">{latest_task}</div>
</div>"""