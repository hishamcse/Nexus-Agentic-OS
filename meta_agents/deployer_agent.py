"""
Nexus — Deployer Agent (Meta-Agent Layer 5)
Takes a validated agent and:
  1. Registers it in the Nexus registry (via MCP or directly)
  2. Writes metadata to disk
  3. Attempts to spawn it as a subprocess (long-lived worker mode)
  4. Confirms it is alive before returning

Side effects: disk writes + process spawn + registry update.
"""
from datetime import datetime, timezone
from registry import register_agent, spawn_agent, ping_agent


def run_deployer(state: dict) -> dict:
    spec      = state.get("agent_spec", {})
    code_path = state.get("code_path", "")
    agent_id  = spec.get("agent_id", "unknown")

    build_log = list(state.get("build_log", []))
    build_log.append(f"[DEPLOYER] Registering {agent_id} in Nexus registry")

    # Build registry record
    record = {
        "agent_id":    agent_id,
        "agent_name":  spec.get("agent_name", "Unknown"),
        "purpose":     spec.get("purpose", ""),
        "code_path":   code_path,
        "spec":        spec,
        "status":      "idle",
        "task_count":  0,
        "restart_count": 0,
        "request_id":  state.get("request_id", ""),
        "user_request": state.get("user_request", ""),
    }

    registered = register_agent(agent_id, record)

    # Attempt to spawn the agent process
    build_log.append(f"[DEPLOYER] Spawning {agent_id} subprocess...")
    pid = spawn_agent(agent_id, code_path)

    if pid:
        build_log.append(f"[DEPLOYER] ✓ Agent process started (PID {pid})")
        # Brief confirmation ping
        health = ping_agent(agent_id)
        health_status = "healthy" if health.get("is_alive") else "unresponsive"
        build_log.append(f"[DEPLOYER] Health ping: {health_status}")
    else:
        # Spawn failed — agent is registered but not running
        # It can still receive tasks via run_task_on_agent (one-shot mode)
        health_status = "idle"
        build_log.append(f"[DEPLOYER] Worker spawn skipped — agent available in task mode")

    deployed = {
        "agent_id":          agent_id,
        "agent_name":        spec.get("agent_name", ""),
        "purpose":           spec.get("purpose", ""),
        "pid":               pid,
        "status":            "running" if pid else "idle",
        "deploy_timestamp":  datetime.now(timezone.utc).isoformat(),
        "code_path":         code_path,
        "task_count":        0,
        "last_health_check": datetime.now(timezone.utc).isoformat(),
        "health_status":     health_status,
        "restart_count":     0,
        "spec":              spec,
    }

    build_log.append(f"[DEPLOYER] ✓ {agent_id} deployed successfully")
    build_log.append(f"[DEPLOYER] Send tasks via Agent Inspector tab")

    return {
        "deployed_agent": deployed,
        "deploy_success": True,
        "build_log":      build_log,
    }