"""
Nexus — Spec Writer Agent (Meta-Agent Layer 2)
Converts the Architect's reasoning into a strict, validated JSON spec
that the Code Generator uses as its exact source of truth.
Output is a fully-formed AgentSpec TypedDict.
"""
import json
import re
import uuid
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, TEMPERATURE

SYSTEM = """You are the Spec Writer inside Nexus Agent OS.
You receive an architect's design brief and produce a precise, validated JSON specification.
The Code Generator will implement this spec exactly — be explicit, not vague.

Return ONLY valid JSON with this exact shape:
{
  "agent_id": "<kebab-case-name-4hexchars>",
  "agent_name": "<Human Readable Name>",
  "purpose": "<one clear sentence>",
  "system_prompt": "<full system prompt for the generated agent — 3-5 sentences, specific>",
  "tools": [
    {
      "name": "<tool_name>",
      "description": "<what this tool does>",
      "implementation": "<builtin|web_search|python_repl|file_reader|custom>"
    }
  ],
  "graph_topology": "<sequential|parallel|loop|react|chain>",
  "entry_point": "run_agent",
  "complexity": "<simple|moderate|complex>",
  "expected_output": "<what the agent returns — data type and description>"
}

Rules:
- agent_id must be kebab-case + 4 random hex chars, e.g. "csv-summariser-a3f2"
- system_prompt must be specific to this agent's domain, not generic
- tools array must match the proposed_tools from the architect
- Keep it implementable — no hallucinated APIs or impossible requirements"""


def run_spec_writer(state: dict) -> dict:
    llm = ChatOpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama",
        model=OLLAMA_MODEL, temperature=max(0.1, TEMPERATURE - 0.1),
    )

    uid = uuid.uuid4().hex[:4]

    prompt = f"""USER REQUEST: {state['user_request']}

ARCHITECT REASONING:
{state.get('architect_reasoning', 'No reasoning provided')}

PROPOSED TOPOLOGY: {state.get('proposed_topology', 'chain')}
PROPOSED TOOLS: {', '.join(state.get('proposed_tools', []))}
COMPLEXITY: {state.get('complexity_estimate', 'simple')}

Use the 4-char suffix "{uid}" in the agent_id.
Write the complete JSON spec. Return JSON only."""

    resp = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])
    spec = _parse(resp.content, uid)
    spec_json = json.dumps(spec, indent=2)

    build_log = list(state.get("build_log", []))
    build_log.append(f"[SPEC WRITER] Agent ID: {spec['agent_id']}")
    build_log.append(f"[SPEC WRITER] Name: {spec['agent_name']}")
    build_log.append(f"[SPEC WRITER] Purpose: {spec['purpose'][:80]}")
    build_log.append(f"[SPEC WRITER] Topology: {spec['graph_topology']} | Tools: {len(spec['tools'])}")

    return {
        "agent_spec": spec,
        "spec_json":  spec_json,
        "build_log":  build_log,
    }


def _parse(text: str, uid: str) -> dict:
    clean = re.sub(r"```(?:json)?", "", text).strip().strip("`")
    clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

    try:
        data = json.loads(clean)
    except Exception:
        # Build a sensible fallback spec
        data = {}

    # Ensure all required keys exist with sensible defaults
    return {
        "agent_id":      data.get("agent_id", f"nexus-agent-{uid}"),
        "agent_name":    data.get("agent_name", "Nexus Agent"),
        "purpose":       data.get("purpose", "General-purpose AI agent"),
        "system_prompt": data.get("system_prompt",
                                  "You are a helpful AI agent. Answer questions accurately and concisely."),
        "tools":         data.get("tools", [{"name": "none", "description": "No tools", "implementation": "builtin"}]),
        "graph_topology": data.get("graph_topology", "chain"),
        "entry_point":   "run_agent",
        "complexity":    data.get("complexity", "simple"),
        "expected_output": data.get("expected_output", "Text response"),
    }