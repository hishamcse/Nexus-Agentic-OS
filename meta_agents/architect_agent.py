"""
Nexus — Architect Agent (Meta-Agent Layer 1)
Reads the user request and decides:
  - What the agent should do (purpose)
  - Which graph topology fits best
  - What tools it needs
  - Complexity level
  - Whether a similar agent already exists in the registry
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, TEMPERATURE, TOPOLOGY_OPTIONS
from registry import list_agents

SYSTEM = """You are the Architect inside Nexus Agent OS — a meta-intelligence whose job is to
design other AI agents. You receive a natural-language request and produce a precise architecture decision.

You must return ONLY valid JSON:
{
  "purpose": "<one clear sentence — what this agent does>",
  "graph_topology": "<sequential|parallel|loop|react|chain>",
  "proposed_tools": ["<tool1>", "<tool2>"],
  "complexity": "<simple|moderate|complex>",
  "architect_reasoning": "<2-3 sentences explaining WHY you chose this topology and these tools>",
  "existing_similar": null
}

TOPOLOGY GUIDE:
- chain: single LLM call, simple Q&A or text transformation
- react: LLM + tool-call loop, needs to search/compute/fetch
- sequential: multi-step pipeline where each step feeds the next
- parallel: multiple specialists run simultaneously, aggregator combines
- loop: iterative refinement, runs until condition met

AVAILABLE TOOLS:
- web_search: search the internet for current information
- python_repl: execute Python code and return results
- file_reader: read text files and documents
- summariser: condense long text into key points
- calculator: perform mathematical computations
- memory_store: persist and retrieve information across sessions

Be precise. Do not over-engineer. A simple chat assistant should be "chain", not "sequential"."""


def run_architect(state: dict) -> dict:
    llm = ChatOpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama",
        model=OLLAMA_MODEL, temperature=TEMPERATURE,
    )

    # Check for similar agents in registry
    existing = list_agents()
    existing_summary = ""
    if existing:
        existing_summary = "EXISTING AGENTS IN REGISTRY:\n" + "\n".join(
            f"  - {a['agent_id']}: {a.get('purpose', a.get('agent_name', '?'))}"
            for a in existing[:10]
        )
    else:
        existing_summary = "EXISTING AGENTS: none yet"

    prompt = f"""USER REQUEST: {state['user_request']}

{existing_summary}

Design the agent. Return JSON only."""

    log_entry = f"[ARCHITECT] Analysing request: \"{state['user_request'][:80]}...\""
    resp = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])
    data = _parse(resp.content)

    # Check for similar existing agent
    existing_similar = None
    if existing:
        req_lower = state["user_request"].lower()
        for agent in existing:
            purpose = agent.get("purpose", "").lower()
            name = agent.get("agent_name", "").lower()
            # Simple keyword overlap check
            req_words = set(req_lower.split())
            agent_words = set((purpose + " " + name).split())
            overlap = req_words & agent_words - {"a", "an", "the", "that", "to", "and", "or", "for"}
            if len(overlap) >= 3:
                existing_similar = agent["agent_id"]
                break

    build_log = list(state.get("build_log", []))
    build_log.append(log_entry)
    build_log.append(f"[ARCHITECT] Topology: {data.get('graph_topology')} | Complexity: {data.get('complexity')}")
    build_log.append(f"[ARCHITECT] Tools: {', '.join(data.get('proposed_tools', []))}")

    return {
        "architect_reasoning":  data.get("architect_reasoning", ""),
        "proposed_topology":    data.get("graph_topology", "chain"),
        "proposed_tools":       data.get("proposed_tools", []),
        "complexity_estimate":  data.get("complexity", "simple"),
        "existing_similar":     existing_similar,
        "build_log":            build_log,
    }


def _parse(text: str) -> dict:
    clean = re.sub(r"```(?:json)?", "", text).strip().strip("`")
    # Handle <think> tags from some models
    clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()
    try:
        return json.loads(clean)
    except Exception:
        # fallback: extract what we can
        topology = "chain"
        for t in TOPOLOGY_OPTIONS:
            if t in clean.lower():
                topology = t
                break
        return {
            "purpose": "General-purpose AI assistant",
            "graph_topology": topology,
            "proposed_tools": ["web_search"],
            "complexity": "simple",
            "architect_reasoning": clean[:200],
            "existing_similar": None,
        }