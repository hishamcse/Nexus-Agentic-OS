"""CSV Analyzer — Generates plain-English statistical summaries of CSV datasets"""
import sys
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen3:8b")

SYSTEM_PROMPT = """The CSV Analyzer processes datasets by first loading the file, then calculating basic statistics, and finally summarizing the results. Provide the CSV file path to begin. The calculator tool computes metrics like mean, median, and standard deviation. The summariser then presents these in human-readable form. Ensure the data is numerical for accurate analysis. When asked to describe your function, respond with a one-sentence summary of your purpose."""

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