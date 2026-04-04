"""
Nexus — Validator Agent (Meta-Agent Layer 4)
Runs the generated code through 3 validation stages in a sandbox:
  1. Syntax check (AST compile — instant)
  2. Import test (subprocess, 150s timeout)
  3. Smoke test (subprocess, 200s timeout)

On failure → routes back to Code Generator (conditional edge in graph).
On pass    → routes forward to Deployer.
Max 3 retries before escalation.
"""
from config import MAX_RETRIES
from sandbox import full_validation


def run_validator(state: dict) -> dict:
    code      = state.get("generated_code", "")
    code_path = state.get("code_path", "")
    attempt   = state.get("generation_attempt", 1)
    spec      = state.get("agent_spec", {})
    agent_id  = spec.get("agent_id", "unknown")

    build_log = list(state.get("build_log", []))
    build_log.append(f"[VALIDATOR] Running 3-stage validation for {agent_id} (attempt {attempt})")

    if not code or not code_path:
        build_log.append("[VALIDATOR] ✗ No code to validate")
        return {
            "validation_result": {
                "status": "fail",
                "stage": "pre_check",
                "error_trace": "No generated code found",
                "import_time_ms": 0.0,
                "test_output": "",
                "attempt": attempt,
            },
            "validation_passed": False,
            "build_log": build_log,
        }

    result = full_validation(code_path, code)
    passed = result["status"] == "pass"

    result["attempt"] = attempt

    if passed:
        build_log.append(f"[VALIDATOR] ✓ All stages passed in {result.get('import_time_ms', 0):.0f}ms")
    else:
        stage      = result.get('stage', 'unknown')
        err_trace  = str(result.get('error_trace') or '(no error message captured)')
        test_out   = str(result.get('test_output') or '')
        # Log the full error — truncate to 200 chars so it's readable in the UI
        err_short  = err_trace[:200]
        build_log.append(f"[VALIDATOR] ✗ Stage '{stage}': {err_short}")
        if test_out and test_out.strip():
            build_log.append(f"[VALIDATOR]   output: {test_out.strip()[:150]}")
        if attempt < MAX_RETRIES:
            build_log.append(f"[VALIDATOR] → Routing back to Code Generator (retry {attempt + 1}/{MAX_RETRIES})")
        else:
            build_log.append(f"[VALIDATOR] ✗ Max retries ({MAX_RETRIES}) reached — escalating to human")
            build_log.append(f"[VALIDATOR]   Final error: {err_trace[:300]}")

    return {
        "validation_result":  result,
        "validation_passed":  passed,
        "escalated":          not passed and attempt >= MAX_RETRIES,
        "build_log":          build_log,
    }


def should_retry(state: dict) -> str:
    """
    LangGraph conditional edge function.
    Called after validator_node to decide next step:
      - "retry"    → back to code_gen_node
      - "deploy"   → forward to deployer_node
      - "escalate" → end with error
    """
    if state.get("validation_passed"):
        return "deploy"
    if state.get("escalated"):
        return "escalate"
    return "retry"