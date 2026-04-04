"""
Nexus — Monitor Agent (Meta-Agent Layer 6)
Two modes:
  1. run_monitor(state) — called once by the main graph after deployment
     to take an initial health snapshot and return reports.
  2. start_monitor_daemon() — background thread that continuously
     polls all agents and restarts crashed ones.

The daemon runs independently of the LangGraph execution — it is a
true background service that keeps the registry healthy.
"""
import threading
import time
from datetime import datetime, timezone
from typing import List
from config import MONITOR_INTERVAL
from registry import list_agents, ping_agent, restart_agent, update_agent


# ── One-shot monitor (called by graph after deploy) ────────────────────────────

def run_monitor(state: dict) -> dict:
    """Called once by the main graph. Takes a health snapshot of all agents."""
    agents = list_agents()
    reports: List[dict] = []

    build_log = list(state.get("build_log", []))
    build_log.append(f"[MONITOR] Health check — {len(agents)} agent(s) in registry")

    for agent in agents:
        agent_id = agent["agent_id"]
        t0 = time.perf_counter()
        health = ping_agent(agent_id)
        elapsed = (time.perf_counter() - t0) * 1000

        report = {
            "agent_id":         agent_id,
            "health_status":    health.get("status", "unknown"),
            "response_time_ms": round(elapsed, 1),
            "task_count":       agent.get("task_count", 0),
            "restart_triggered": False,
            "notes":            "",
        }

        if not health.get("is_alive") and agent.get("status") == "running":
            # Agent was supposed to be running but isn't — restart
            new_pid = restart_agent(agent_id)
            report["restart_triggered"] = True
            report["notes"] = f"Restarted — new PID {new_pid}"
            build_log.append(f"[MONITOR] ⚠ {agent_id} was unresponsive — restarted (PID {new_pid})")
        else:
            status_icon = "✓" if health.get("is_alive") else "○"
            build_log.append(f"[MONITOR] {status_icon} {agent_id}: {health.get('status', 'unknown')}")

        reports.append(report)

    if not agents:
        build_log.append("[MONITOR] No agents registered yet — monitor standing by")

    return {
        "monitor_reports": reports,
        "build_log":       build_log,
    }


# ── Background daemon ──────────────────────────────────────────────────────────

_daemon_thread: threading.Thread = None
_daemon_running = False


def start_monitor_daemon():
    """
    Start the background monitor daemon.
    Safe to call multiple times — only one daemon runs at a time.
    """
    global _daemon_thread, _daemon_running

    if _daemon_running and _daemon_thread and _daemon_thread.is_alive():
        return   # already running

    _daemon_running = True
    _daemon_thread = threading.Thread(target=_daemon_loop, daemon=True, name="nexus-monitor")
    _daemon_thread.start()


def stop_monitor_daemon():
    global _daemon_running
    _daemon_running = False


def _daemon_loop():
    """Main daemon loop — runs every MONITOR_INTERVAL seconds."""
    global _daemon_running
    while _daemon_running:
        try:
            _check_all_agents()
        except Exception:
            pass    # Never let the daemon crash silently propagate
        time.sleep(MONITOR_INTERVAL)


def _check_all_agents():
    """Health-check every registered agent and restart crashed ones."""
    agents = list_agents()
    now = datetime.now(timezone.utc).isoformat()

    for agent in agents:
        agent_id = agent["agent_id"]
        if agent.get("status") == "stopped":
            continue   # deliberately stopped, don't touch

        health = ping_agent(agent_id)
        update_agent(agent_id, {"last_health_check": now})

        # Auto-restart if was running but now unresponsive
        if not health.get("is_alive") and agent.get("status") == "running":
            restart_count = agent.get("restart_count", 0)
            if restart_count < 5:   # max 5 auto-restarts
                restart_agent(agent_id)


def get_daemon_status() -> dict:
    return {
        "running": _daemon_running,
        "alive":   _daemon_thread.is_alive() if _daemon_thread else False,
        "interval_seconds": MONITOR_INTERVAL,
    }