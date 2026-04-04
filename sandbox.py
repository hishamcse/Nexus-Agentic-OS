"""
Nexus Agent OS — Sandbox Executor
Safely runs generated agent code in an isolated subprocess.
Used by the Validator agent to smoke-test generated code before deployment.

Safety measures:
  - subprocess with stdout/stderr capture (no terminal access)
  - configurable timeout (default 15s)
  - restricted environment (strips sensitive env vars)
  - working directory scoped to generated agent folder
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional


BLOCKED_ENV_KEYS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID", "GOOGLE_API_KEY", "DATABASE_URL",
}

MAX_OUTPUT_BYTES = 8_192   # 8 KB cap on stdout/stderr


def _safe_env() -> dict:
    """Strip sensitive keys from the environment."""
    return {k: v for k, v in os.environ.items() if k not in BLOCKED_ENV_KEYS}


def run_import_test(code_path: str, timeout: int = 15) -> dict:
    """
    Test 1: Can the generated agent.py be imported without errors?
    Runs: python -c "import importlib.util; spec = importlib.util.spec_from_file_location(...)"
    """
    agent_py = Path(code_path) / "agent.py"
    if not agent_py.exists():
        return {
            "success": False,
            "error": f"agent.py not found at {code_path}",
            "elapsed_ms": 0,
        }

    check_code = f"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("agent", r"{agent_py}")
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    print("IMPORT_OK")
except Exception as e:
    print(f"IMPORT_FAIL: {{e}}")
    sys.exit(1)
"""
    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-c", check_code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(code_path)),
            env=_safe_env(),
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        success = result.returncode == 0 and "IMPORT_OK" in result.stdout
        return {
            "success": success,
            "stdout": result.stdout[:MAX_OUTPUT_BYTES],
            "stderr": result.stderr[:MAX_OUTPUT_BYTES],
            "elapsed_ms": elapsed,
            "error": result.stderr.strip()[:500] if not success else None,
        }
    except subprocess.TimeoutExpired:
        elapsed = int((time.perf_counter() - start) * 1000)
        return {"success": False, "error": f"Import timed out after {timeout}s", "elapsed_ms": elapsed}
    except Exception as e:
        return {"success": False, "error": str(e), "elapsed_ms": 0}


def run_smoke_test(code_path: str, test_script: Optional[str] = None, timeout: int = 30) -> dict:
    """
    Test 3: Run the generated agent in --mode test directly (no nested subprocess).
    Checks for TEST_OK in stdout.
    """
    agent_dir = Path(code_path)
    agent_py  = agent_dir / "agent.py"

    if not agent_py.exists():
        return {"success": False, "error": "agent.py not found", "elapsed_ms": 0}

    # Run agent.py --mode test directly — avoids nested subprocess timeout issues
    cmd = [sys.executable, str(agent_py), "--mode", "test"]

    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(agent_dir),
            env=_safe_env(),
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        stdout  = result.stdout[:MAX_OUTPUT_BYTES]
        stderr  = result.stderr[:MAX_OUTPUT_BYTES]
        success = result.returncode == 0 and "TEST_OK" in stdout

        # Build a useful error message from both stdout and stderr
        if not success:
            parts = []
            if stdout.strip():
                parts.append(f"stdout: {stdout.strip()[:400]}")
            if stderr.strip():
                parts.append(f"stderr: {stderr.strip()[:400]}")
            error_msg = " | ".join(parts) if parts else f"exit_code={result.returncode}, no output"
        else:
            error_msg = None

        return {
            "success":    success,
            "stdout":     stdout,
            "stderr":     stderr,
            "elapsed_ms": elapsed,
            "exit_code":  result.returncode,
            "error":      error_msg,
        }
    except subprocess.TimeoutExpired:
        elapsed = int((time.perf_counter() - start) * 1000)
        return {"success": False, "error": f"Smoke test timed out after {timeout}s — agent LLM call may be too slow", "elapsed_ms": elapsed}
    except Exception as e:
        return {"success": False, "error": str(e), "elapsed_ms": 0}


def run_syntax_check(code: str) -> dict:
    """
    Quick AST-level syntax check on the generated code string.
    No subprocess needed — uses Python's compile() built-in.
    """
    try:
        compile(code, "<generated>", "exec")
        return {"success": True, "error": None}
    except SyntaxError as e:
        return {
            "success": False,
            "error": f"SyntaxError at line {e.lineno}: {e.msg}",
            "lineno": e.lineno,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def full_validation(code_path: str, generated_code: str, test_script: Optional[str] = None) -> dict:
    """
    Run all three validation stages in order:
      1. Syntax check (fast, no subprocess)
      2. Import test (subprocess, 15s timeout)
      3. Smoke test (subprocess, 20s timeout)

    Returns a combined result dict.
    The optional `test_script` arg is kept only for backward compatibility.
    """
    # Stage 1: Syntax
    syntax = run_syntax_check(generated_code)
    if not syntax["success"]:
        return {
            "status": "fail",
            "stage": "syntax",
            "error_trace": syntax["error"],
            "import_time_ms": 0.0,
            "test_output": "",
        }

    # Stage 2: Import
    imp = run_import_test(code_path, timeout=15)
    if not imp["success"]:
        return {
            "status": "fail",
            "stage": "import",
            "error_trace": imp.get("error", "Import failed"),
            "import_time_ms": float(imp.get("elapsed_ms", 0)),
            "test_output": imp.get("stdout", ""),
        }

    # Stage 3: Smoke test — run agent.py --mode test directly (30s timeout for LLM call)
    smoke = run_smoke_test(code_path, test_script=None, timeout=30)

    # Use stdout as test_output (contains TEST_OK or the actual output)
    test_out = smoke.get("stdout", "") or smoke.get("stderr", "")

    return {
        "status": "pass" if smoke["success"] else "fail",
        "stage": "all_passed" if smoke["success"] else "smoke_test",
        "error_trace": smoke.get("error") if not smoke["success"] else None,
        "import_time_ms": float(imp.get("elapsed_ms", 0)),
        "test_output": test_out[:2000],
    }