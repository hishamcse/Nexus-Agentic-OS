"""Marketing Ideas Generator Agent"""
import sys
import os
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
SYSTEM_PROMPT = """You are a marketing strategy expert. When given a product concept, brainstorm 10 unique angles that highlight its value proposition. For each idea, provide a concise one-sentence pitch that emphasizes emotional benefits, unique features, or solving specific problems. Focus on creativity and diversity in approach."""

def run_agent(input_text: str) -> str:
    model = ChatOpenAI(
        base_url=OLLAMA_BASE_URL,
        model_name=OLLAMA_MODEL,
        temperature=0.7
    )
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=input_text)
    ]
    
    response = model.invoke(messages)
    pitches = [{"pitch": pitch} for pitch in response.content.split("\n")[:10]]
    return json.dumps(pitches, ensure_ascii=False)

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