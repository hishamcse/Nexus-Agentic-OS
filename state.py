"""
Nexus Agent OS — Shared State
Every meta-agent reads and writes slots in NexusState.
The state travels through the full graph: Architect → Spec → CodeGen → Validator → Deployer → Monitor.
"""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class ToolSpec(TypedDict):
    name: str
    description: str
    implementation: str        # "builtin" | "web_search" | "python_repl" | "custom"


class AgentSpec(TypedDict):
    agent_id: str              # unique slug, e.g. "data-summariser-a3f2"
    agent_name: str            # human name, e.g. "Data Summariser"
    purpose: str               # one-sentence purpose
    system_prompt: str         # full system prompt for the generated agent
    tools: List[ToolSpec]
    graph_topology: str        # "sequential" | "parallel" | "loop" | "react" | "chain"
    entry_point: str           # name of the main function
    complexity: str            # "simple" | "moderate" | "complex"
    expected_output: str       # description of what the agent produces


class ValidationResult(TypedDict):
    status: str                # "pass" | "fail"
    error_trace: Optional[str]
    import_time_ms: float
    test_output: str
    attempt: int


class DeployedAgent(TypedDict):
    agent_id: str
    agent_name: str
    purpose: str
    pid: Optional[int]
    status: str                # "running" | "idle" | "crashed" | "stopped"
    deploy_timestamp: str
    code_path: str
    task_count: int
    last_health_check: str
    health_status: str         # "healthy" | "unresponsive" | "unknown"
    restart_count: int
    spec: AgentSpec


class MonitorReport(TypedDict):
    agent_id: str
    health_status: str
    response_time_ms: float
    task_count: int
    restart_triggered: bool
    notes: str


class NexusState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    request_id: str
    user_request: str          # "Build me an agent that summarises CSV files"

    # ── Architect output ───────────────────────────────────────────────────
    architect_reasoning: str   # free-text reasoning trace
    proposed_topology: str
    proposed_tools: List[str]
    complexity_estimate: str
    existing_similar: Optional[str]   # agent_id if similar exists

    # ── Spec Writer output ─────────────────────────────────────────────────
    agent_spec: Optional[AgentSpec]
    spec_json: str             # raw JSON string of the spec

    # ── Code Generator output ──────────────────────────────────────────────
    generated_code: str        # full content of agent.py
    generated_test: str        # content of smoke_test.py
    code_path: str             # path to generated_agents/{agent_id}/
    generation_attempt: int    # tracks retry count

    # ── Validator output ───────────────────────────────────────────────────
    validation_result: Optional[ValidationResult]
    validation_passed: bool

    # ── Deployer output ────────────────────────────────────────────────────
    deployed_agent: Optional[DeployedAgent]
    deploy_success: bool

    # ── Monitor output ─────────────────────────────────────────────────────
    monitor_reports: List[MonitorReport]

    # ── Build log (streamed to UI) ─────────────────────────────────────────
    build_log: List[str]       # timestamped events shown in Build Log tab

    # ── Error handling ─────────────────────────────────────────────────────
    error: Optional[str]
    escalated: bool            # True if max retries exceeded