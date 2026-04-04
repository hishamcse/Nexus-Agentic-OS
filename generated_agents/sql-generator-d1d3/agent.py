"""Agent docstring"""
import sys, os, json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen3:8b")
SYSTEM_PROMPT   = """You are a SQL query generator that translates natural language requests into precise SQL. When given a query like 'show me all orders from last month', you: 1) Identify the target table (orders), 2) Parse temporal filters (last month = DATE_SUB(NOW(), INTERVAL 1 MONTH)), 3) Construct valid SQL with proper syntax. Output only the SQL statement without explanation. Use DATE_SUB for date calculations and ensure proper table aliases."""

def run_agent(input_text: str) -> str:
    model = ChatOpenAI(
        base_url=OLLAMA_BASE_URL,
        model_name=OLLAMA_MODEL,
        temperature=0
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=input_text)
    ]
    response = model.invoke(messages)
    return response.content

if __name__ == "__main__":
    mode = "task"
    input_text = "Hello"
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--mode" and i+1 < len(sys.argv[1:]): mode = sys.argv[i+2]
        if arg == "--input" and i+1 < len(sys.argv[1:]): input_text = sys.argv[i+2]
    if mode == "test":
        result = run_agent("test input: describe what you do in one sentence")
        print(f"TEST_OK: {result[:100]}")
    elif mode == "task":
        result = run_agent(input_text)
        print(result)
    elif mode == "worker":
        print(f"WORKER_READY: {os.getenv('NEXUS_AGENT_ID', 'unknown')}")
        import time
        while True: time.sleep(10)