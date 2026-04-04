"""
Nexus Agent OS — Agent Registry
Manages the full lifecycle of deployed agents:
  register → spawn → health-check → restart → deregister

Each agent runs as an isolated subprocess.
The registry is persisted to memory/registry.json so it survives restarts.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from memory_store import add_memory, get_context_block

MEMORY_DIR  = Path(__file__).parent / "memory"
REGISTRY_FILE = MEMORY_DIR / "registry.json"
MEMORY_DIR.mkdir(exist_ok=True)

_lock = threading.Lock()


# ── Registry CRUD ──────────────────────────────────────────────────────────────

def _load() -> Dict[str, dict]:
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text())
        except Exception:
            pass
    return {}


def _save(registry: Dict[str, dict]) -> None:
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2))


def register_agent(agent_id: str, record: dict) -> dict:
    """Add or update an agent record in the registry."""
    with _lock:
        reg = _load()
        record["agent_id"]         = agent_id
        record["deploy_timestamp"] = datetime.now(timezone.utc).isoformat()
        record["task_count"]       = record.get("task_count", 0)
        record["restart_count"]    = record.get("restart_count", 0)
        record["status"]           = record.get("status", "idle")
        record["health_status"]    = "unknown"
        record["last_health_check"] = ""
        reg[agent_id] = record
        _save(reg)
    return record


def get_agent(agent_id: str) -> Optional[dict]:
    with _lock:
        return _load().get(agent_id)


def list_agents() -> List[dict]:
    with _lock:
        return list(_load().values())


def update_agent(agent_id: str, updates: dict) -> Optional[dict]:
    with _lock:
        reg = _load()
        if agent_id not in reg:
            return None
        reg[agent_id].update(updates)
        _save(reg)
        return reg[agent_id]


def deregister_agent(agent_id: str) -> bool:
    with _lock:
        reg = _load()
        if agent_id in reg:
            del reg[agent_id]
            _save(reg)
            return True
        return False


# ── Subprocess lifecycle ───────────────────────────────────────────────────────

# Maps agent_id → subprocess.Popen
_processes: Dict[str, subprocess.Popen] = {}
_process_lock = threading.Lock()


def spawn_agent(agent_id: str, code_path: str) -> Optional[int]:
    """
    Spawn an agent subprocess that runs agent.py in the generated_agents folder.
    Returns the PID on success, None on failure.
    The subprocess runs as a long-lived worker process.
    """
    agent_py = Path(code_path) / "agent.py"
    if not agent_py.exists():
        return None

    try:
        proc = subprocess.Popen(
            [sys.executable, str(agent_py), "--mode", "worker"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(code_path)),
            env={**os.environ, "NEXUS_AGENT_ID": agent_id},
        )
        with _process_lock:
            _processes[agent_id] = proc
        update_agent(agent_id, {"pid": proc.pid, "status": "running"})
        return proc.pid
    except Exception as e:
        update_agent(agent_id, {"status": "crashed", "health_status": "unresponsive"})
        return None


def ping_agent(agent_id: str) -> dict:
    """
    Health check an agent process.
    Returns status dict with is_alive, pid, status.
    """
    with _process_lock:
        proc = _processes.get(agent_id)

    record = get_agent(agent_id)
    if not record:
        return {"is_alive": False, "status": "not_found", "pid": None}

    pid = record.get("pid")

    # Check if process object exists and is running
    if proc is not None:
        ret = proc.poll()
        if ret is None:
            # Process is alive
            ts = datetime.now(timezone.utc).isoformat()
            update_agent(agent_id, {
                "health_status": "healthy",
                "last_health_check": ts,
                "status": "running",
            })
            return {"is_alive": True, "status": "running", "pid": proc.pid}
        else:
            # Process has exited
            update_agent(agent_id, {
                "health_status": "unresponsive",
                "status": "crashed",
                "last_health_check": datetime.now(timezone.utc).isoformat(),
            })
            return {"is_alive": False, "status": "crashed", "pid": pid, "exit_code": ret}

    # No process object — check by PID if we have one
    if pid:
        try:
            os.kill(pid, 0)   # signal 0 = just check existence
            update_agent(agent_id, {"health_status": "healthy", "status": "running",
                                    "last_health_check": datetime.now(timezone.utc).isoformat()})
            return {"is_alive": True, "status": "running", "pid": pid}
        except (ProcessLookupError, PermissionError):
            pass

    update_agent(agent_id, {"health_status": "unresponsive", "status": "idle",
                             "last_health_check": datetime.now(timezone.utc).isoformat()})
    return {"is_alive": False, "status": "idle", "pid": pid}


def restart_agent(agent_id: str) -> Optional[int]:
    """Kill the current process (if any) and re-spawn."""
    stop_agent(agent_id)
    time.sleep(0.5)
    record = get_agent(agent_id)
    if not record:
        return None
    code_path = record.get("code_path", "")
    restart_count = record.get("restart_count", 0) + 1
    update_agent(agent_id, {"restart_count": restart_count})
    return spawn_agent(agent_id, code_path)


def stop_agent(agent_id: str) -> bool:
    """Gracefully stop an agent process."""
    with _process_lock:
        proc = _processes.pop(agent_id, None)
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
    update_agent(agent_id, {"status": "stopped", "pid": None})
    return True


def run_task_on_agent(agent_id: str, task: str) -> dict:
    """
    Send a task to a deployed agent by running its agent.py in task mode.
    Returns the output dict from the agent.
    This is a simple subprocess call — the agent runs, produces output, exits.
    """
    record = get_agent(agent_id)
    if not record:
        return {"error": "Agent not found", "agent_id": agent_id}

    code_path = record.get("code_path", "")
    agent_py  = Path(code_path) / "agent.py"
    if not agent_py.exists():
        return {"error": "Agent file not found", "agent_id": agent_id}

    try:
        context_block = get_context_block(agent_id)
        prepared_task = task
        if context_block:
            prepared_task = f"{context_block}\n\n[CURRENT TASK]\n{task}"

        started = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(agent_py), "--mode", "task", "--input", prepared_task],
            capture_output=True, text=True, timeout=600,
            cwd=str(Path(code_path)),
            env={**os.environ, "NEXUS_AGENT_ID": agent_id},
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()[:500] if result.stderr else ""
        primary_output = stdout or stderr

        update_agent(agent_id, {
            "task_count": record.get("task_count", 0) + 1,
            "status": "idle" if result.returncode == 0 else "crashed",
            "last_task_at": datetime.now(timezone.utc).isoformat(),
            "last_task_duration_ms": duration_ms,
        })

        if primary_output:
            add_memory(agent_id, task, primary_output)

        return {
            "agent_id":  agent_id,
            "task":      task,
            "stdout":    stdout,
            "stderr":    stderr,
            "exit_code": result.returncode,
            "success":   result.returncode == 0,
            "duration_ms": duration_ms,
            "context_injected": bool(context_block),
        }
    except subprocess.TimeoutExpired:
        return {"error": "Task timed out after 600s", "agent_id": agent_id}
    except Exception as e:
        return {"error": str(e), "agent_id": agent_id}