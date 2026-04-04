"""
Nexus Agent OS — Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR          = Path(__file__).resolve().parent
MEMORY_DIR        = BASE_DIR / "memory"
GENERATED_DIR     = BASE_DIR / "generated_agents"
TEMPLATES_DIR     = BASE_DIR / "templates"

for d in (MEMORY_DIR, GENERATED_DIR, TEMPLATES_DIR):
    d.mkdir(exist_ok=True)

OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL      = os.getenv("OLLAMA_BASE_MODEL", "qwen3:8b")
TEMPERATURE       = float(os.getenv("NEXUS_TEMPERATURE", "0.3"))

MAX_RETRIES       = int(os.getenv("NEXUS_MAX_RETRIES", "3"))
MONITOR_INTERVAL  = int(os.getenv("NEXUS_MONITOR_INTERVAL", "30"))   # seconds
SANDBOX_TIMEOUT   = int(os.getenv("NEXUS_SANDBOX_TIMEOUT", "150"))

# Topology options the Architect can choose from
TOPOLOGY_OPTIONS = [
    "sequential",   # A → B → C → D
    "parallel",     # A → [B ‖ C ‖ D] → E
    "loop",         # A → B → [continue|end]
    "react",        # ReAct tool-call loop
    "chain",        # simple LLM chain, single node
]