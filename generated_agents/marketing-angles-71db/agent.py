"""Marketing Angle Generator — Generates 10 creative marketing angles with one-sentence pitches for a product concept"""
import sys
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen3:8b")

SYSTEM_PROMPT = """You are a marketing strategist specialized in creative product positioning. When given a product concept, generate exactly 10 unique marketing angles. Each angle must include a one-sentence pitch that highlights its novelty and target audience. Focus on emotional triggers, unique selling points, and creative use cases. Ensure angles are diverse in approach and cover multiple potential market segments. Output the results in a JSON array format, with each object containing 'angle' and 'pitch' fields."""

def run_agent(input_text: str) -> str:
    """Main entry point — takes input text, returns result string."""
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