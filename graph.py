"""
Nexus Agent OS — LangGraph Meta-Graph
Architecture: Plan-then-Execute with Conditional Retry Loop

Flow:
  bootstrap → architect → spec_writer → code_gen → validator
                                              ↑          |
                                              └── retry ──┤
                                                          |
                                                       deploy → monitor → END
                                                          |
                                                      escalate → END (error)

The conditional edge after validator is the unique feature:
  - pass  → deployer
  - retry → code_gen (with error context)
  - escalate → end (max retries exceeded)
"""
import json
import uuid

from langgraph.graph import END, START, StateGraph

from meta_agents.architect_agent  import run_architect
from meta_agents.spec_writer_agent import run_spec_writer
from meta_agents.code_gen_agent    import run_code_gen
from meta_agents.validator_agent   import run_validator, should_retry
from meta_agents.deployer_agent    import run_deployer
from meta_agents.monitor_agent     import run_monitor
from state import NexusState


# ── Node wrappers ──────────────────────────────────────────────────────────────

def bootstrap_node(state: NexusState) -> dict:
    request_id = state.get("request_id") or uuid.uuid4().hex[:10]
    return {
        "request_id":         request_id,
        "generation_attempt": 0,
        "validation_passed":  False,
        "deploy_success":     False,
        "escalated":          False,
        "monitor_reports":    [],
        "build_log":          [f"[NEXUS] Request {request_id} received"],
        "error":              None,
    }


def architect_node(state: NexusState) -> dict:
    return run_architect(state)


def spec_writer_node(state: NexusState) -> dict:
    return run_spec_writer(state)


def code_gen_node(state: NexusState) -> dict:
    return run_code_gen(state)


def validator_node(state: NexusState) -> dict:
    return run_validator(state)


def deployer_node(state: NexusState) -> dict:
    return run_deployer(state)


def monitor_node(state: NexusState) -> dict:
    return run_monitor(state)


def escalate_node(state: NexusState) -> dict:
    spec     = state.get("agent_spec", {})
    agent_id = spec.get("agent_id", "unknown") if spec else "unknown"
    val      = state.get("validation_result", {})
    attempts = state.get("generation_attempt", 0)

    error_trace = (val.get("error_trace") or "unknown") if val else "unknown"
    test_output = (val.get("test_output") or "") if val else ""
    stage       = (val.get("stage") or "unknown") if val else "unknown"

    error_msg = (
        f"Agent {agent_id} failed validation after {attempts} attempt(s). "
        f"Stage: {stage} | Error: {error_trace[:300]}"
        + (f" | Output: {test_output.strip()[:200]}" if test_output.strip() else "")
    )
    build_log = list(state.get("build_log", []))
    build_log.append(f"[NEXUS] ✗ Escalated — {error_msg}")
    build_log.append(f"[NEXUS] Tip: check generated_agents/{agent_id}/agent.py and run it manually")
    return {"error": error_msg, "build_log": build_log}


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(NexusState)

    g.add_node("bootstrap",    bootstrap_node)
    g.add_node("architect",    architect_node)
    g.add_node("spec_writer",  spec_writer_node)
    g.add_node("code_gen",     code_gen_node)
    g.add_node("validator",    validator_node)
    g.add_node("deployer",     deployer_node)
    g.add_node("monitor",      monitor_node)
    g.add_node("escalate",     escalate_node)

    # Main flow
    g.add_edge(START,         "bootstrap")
    g.add_edge("bootstrap",   "architect")
    g.add_edge("architect",   "spec_writer")
    g.add_edge("spec_writer", "code_gen")
    g.add_edge("code_gen",    "validator")

    # ── Conditional retry loop ──────────────────────────────────────────────
    g.add_conditional_edges(
        "validator",
        should_retry,
        {
            "deploy":   "deployer",
            "retry":    "code_gen",     # ← the loop-back edge
            "escalate": "escalate",
        },
    )

    g.add_edge("deployer",  "monitor")
    g.add_edge("monitor",   END)
    g.add_edge("escalate",  END)

    return g.compile()


# ── Public engine ──────────────────────────────────────────────────────────────

class NexusEngine:
    def __init__(self):
        self.graph = build_graph()

    def forge(self, user_request: str) -> NexusState:
        """
        Full agent forge pipeline.
        Returns the final NexusState after all nodes have run.
        """
        initial: NexusState = {
            "request_id":          "",
            "user_request":        user_request,
            "architect_reasoning": "",
            "proposed_topology":   "",
            "proposed_tools":      [],
            "complexity_estimate": "",
            "existing_similar":    None,
            "agent_spec":          None,
            "spec_json":           "",
            "generated_code":      "",
            "generated_test":      "",
            "code_path":           "",
            "generation_attempt":  0,
            "validation_result":   None,
            "validation_passed":   False,
            "deployed_agent":      None,
            "deploy_success":      False,
            "monitor_reports":     [],
            "build_log":           [],
            "error":               None,
            "escalated":           False,
        }
        return self.graph.invoke(initial)

    def forge_stream(self, user_request: str):
        """
        Stream the graph execution — yields (node_name, state_update) tuples.
        Useful for streaming build log events to the UI.
        """
        initial: NexusState = {
            "request_id":          "",
            "user_request":        user_request,
            "architect_reasoning": "",
            "proposed_topology":   "",
            "proposed_tools":      [],
            "complexity_estimate": "",
            "existing_similar":    None,
            "agent_spec":          None,
            "spec_json":           "",
            "generated_code":      "",
            "generated_test":      "",
            "code_path":           "",
            "generation_attempt":  0,
            "validation_result":   None,
            "validation_passed":   False,
            "deployed_agent":      None,
            "deploy_success":      False,
            "monitor_reports":     [],
            "build_log":           [],
            "error":               None,
            "escalated":           False,
        }
        for event in self.graph.stream(initial):
            yield event