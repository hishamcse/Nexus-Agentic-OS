"""
Nexus — Code Generator Agent (Meta-Agent Layer 3)
Takes the validated JSON spec and generates a complete, runnable Python agent.
Writes agent.py and smoke_test.py into generated_agents/{agent_id}/.

This is the most complex meta-agent — it generates real LangGraph code,
not wrappers around chat models.
"""
import json
import re
import textwrap
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, TEMPERATURE, GENERATED_DIR

SYSTEM = """You are the Code Generator inside Nexus Agent OS.
You receive a JSON agent spec and generate a complete, self-contained, runnable Python file.

CRITICAL RULES:
1. Generate ONLY the Python code — no markdown, no backticks, no explanation
2. The file must work with: python agent.py --mode test   (MUST print "TEST_OK:" prefix)
3. The file must work with: python agent.py --mode task --input "some text"
4. Use langchain_openai.ChatOpenAI with base_url from environment
5. Import everything the code needs — assume standard library + langchain + langgraph only
6. The run_agent(input_text: str) -> str function is the entry point
7. Wrap all LLM calls in try/except — return a fallback string on error
8. NEVER use input() or any interactive functions

EXACT TEMPLATE — follow this structure precisely:

\"\"\"<Agent name> — <one line description>\"\"\"
import sys
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen3:8b")

SYSTEM_PROMPT = \"\"\"<specific system prompt for this agent's task>\"\"\"


def run_agent(input_text: str) -> str:
    \"\"\"Main entry point — takes input text, returns result string.\"\"\"
    try:
        llm = ChatOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            model=OLLAMA_MODEL,
            temperature=0.3,
        )
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=input_text)]
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mode = "task"
    input_text = "test query"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
        if arg == "--input" and i + 1 < len(args):
            input_text = args[i + 1]

    if mode == "test":
        result = run_agent("describe what you do in one sentence")
        print(f"TEST_OK: {result[:100]}")
    elif mode == "task":
        result = run_agent(input_text)
        print(result)
    elif mode == "worker":
        import time
        agent_id = os.getenv("NEXUS_AGENT_ID", "unknown")
        print(f"WORKER_READY: {agent_id}", flush=True)
        while True:
            time.sleep(10)

Use this template as the base. Customise SYSTEM_PROMPT and run_agent logic for the spec.
For sequential/parallel/loop topologies, add helper functions inside run_agent.
Keep it simple — the goal is a working agent, not the most complex implementation.
Generate the COMPLETE file. No markdown fences. Start with the docstring triple-quote."""


SMOKE_TEST_TEMPLATE = '''"""Smoke test for {agent_name}"""
import subprocess, sys

result = subprocess.run(
    [sys.executable, "agent.py", "--mode", "test"],
    capture_output=True, text=True, timeout=150
)
if "TEST_OK" in result.stdout:
    print("SMOKE_PASS")
    sys.exit(0)
else:
    print(f"SMOKE_FAIL: {{result.stdout}} {{result.stderr}}")
    sys.exit(1)
'''


def run_code_gen(state: dict) -> dict:
    llm = ChatOpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama",
        model=OLLAMA_MODEL, temperature=TEMPERATURE + 0.05,
    )

    spec = state.get("agent_spec", {})
    attempt = state.get("generation_attempt", 0) + 1

    # Include previous error if this is a retry
    retry_context = ""
    if attempt > 1:
        prev_result = state.get("validation_result", {})
        if prev_result:
            stage      = prev_result.get('stage', 'unknown')
            error      = prev_result.get('error_trace', 'unknown error') or 'unknown error'
            test_out   = prev_result.get('test_output', '') or ''
            retry_context = f"""
PREVIOUS ATTEMPT FAILED — YOU MUST FIX THIS:
Stage that failed: {stage}
Error message: {error[:400]}
Agent output during test: {test_out[:300] if test_out.strip() else '(no output)'}

The smoke test runs: python agent.py --mode test
It expects "TEST_OK:" to appear in stdout.
Ensure:
  1. The --mode test branch prints exactly: print(f"TEST_OK: {{result[:100]}}")
  2. The LLM call is wrapped in try/except returning a fallback string
  3. No interactive prompts, no input() calls
  4. All imports exist in the standard library or langchain/langgraph packages"""

    prompt = f"""Generate a complete Python agent file for this spec:

{state.get('spec_json', json.dumps(spec, indent=2))}

USER REQUEST CONTEXT: {state.get('user_request', '')}
{retry_context}

Generate ONLY the Python file content. No markdown. No explanation. Start with the docstring."""

    resp = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])
    code = _clean_code(resp.content)

    # Write files to disk
    agent_id  = spec.get("agent_id", "unknown-agent")
    agent_dir = GENERATED_DIR / agent_id
    agent_dir.mkdir(exist_ok=True)

    agent_py   = agent_dir / "agent.py"
    test_py    = agent_dir / "smoke_test.py"
    spec_json  = agent_dir / "spec.json"

    agent_py.write_text(code)
    smoke = SMOKE_TEST_TEMPLATE.format(agent_name=spec.get("agent_name", "Agent"))
    test_py.write_text(smoke)
    spec_json.write_text(state.get("spec_json", "{}"))

    build_log = list(state.get("build_log", []))
    build_log.append(f"[CODE GEN] Attempt {attempt} — writing {agent_id}/agent.py ({len(code)} chars)")
    build_log.append(f"[CODE GEN] Topology implemented: {spec.get('graph_topology', 'chain')}")

    return {
        "generated_code":    code,
        "generated_test":    smoke,
        "code_path":         str(agent_dir),
        "generation_attempt": attempt,
        "build_log":         build_log,
    }


def _clean_code(text: str) -> str:
    """Strip markdown fences and <think> tags from generated code."""
    # Remove think tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Remove markdown code fences
    text = re.sub(r"^```(?:python)?\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    return text.strip()